"""
LION backbone integrated into CenterPoint.

Hybrid architecture: SpConv stem (from SpMiddleResNetFHD) for spatial downsampling
followed by LION body (windowed sequence modeling with Mamba/SSM operators).

Core LION modules adapted from:
    LION/pcdet/models/backbones_3d/lion_backbone_one_stride.py
"""
from functools import partial
from types import SimpleNamespace
import math
import numpy as np

import torch
import torch.nn as nn
from torch.nn import functional as F

try:
    import spconv.pytorch as spconv
    from spconv.pytorch import SparseConv3d, SubMConv3d
except ImportError:
    import spconv
    from spconv import SparseConv3d, SubMConv3d

from mamba_ssm import Mamba
from timm.models.layers import DropPath
import torch.utils.checkpoint as cp

from det3d.core.utils.scatter import scatter_sum
from ..registry import BACKBONES
from ..utils import build_norm_layer


class MambaBlock(nn.Module):
    """
    Compatibility wrapper matching the LION-expected Block interface
    (d_model, d_state, d_conv, expand, drop_path, layer_id, n_layer, with_cp)
    around mamba_ssm v2.x's Mamba class.
    """

    def __init__(self, d_model, d_state=16, d_conv=4, expand=2,
                 drop_path=0.0, layer_id=0, n_layer=1, with_cp=False, **kwargs):
        super().__init__()
        self.norm = nn.LayerNorm(d_model)
        self.mixer = Mamba(d_model=d_model, d_state=d_state,
                           d_conv=d_conv, expand=expand, layer_idx=layer_id)
        self.drop_path = DropPath(drop_path) if drop_path > 0.0 else nn.Identity()
        self.with_cp = with_cp

    def _inner_forward(self, x):
        return x + self.drop_path(self.mixer(self.norm(x)))

    def forward(self, x):
        return self._inner_forward(x)


LinearOperatorMap = {"Mamba": MambaBlock}


# ---------------------------------------------------------------------------
#  Sparse-tensor utility
# ---------------------------------------------------------------------------
def replace_feature(out, new_features):
    if "replace_feature" in out.__dir__():
        return out.replace_feature(new_features)
    else:
        out.features = new_features
        return out


# ---------------------------------------------------------------------------
#  SpConv building blocks (same as scn.py)
# ---------------------------------------------------------------------------
def _conv3x3(in_planes, out_planes, stride=1, indice_key=None, bias=True):
    return SubMConv3d(
        in_planes, out_planes, kernel_size=3,
        stride=stride, padding=1, bias=bias, indice_key=indice_key,
    )


class _SparseBasicBlock(spconv.SparseModule):
    expansion = 1

    def __init__(self, inplanes, planes, stride=1, norm_cfg=None,
                 downsample=None, indice_key=None):
        super().__init__()
        if norm_cfg is None:
            norm_cfg = dict(type="BN1d", eps=1e-3, momentum=0.01)
        bias = norm_cfg is not None
        self.conv1 = _conv3x3(inplanes, planes, stride, indice_key=indice_key, bias=bias)
        self.bn1 = build_norm_layer(norm_cfg, planes)[1]
        self.relu = nn.ReLU()
        self.conv2 = _conv3x3(planes, planes, indice_key=indice_key, bias=bias)
        self.bn2 = build_norm_layer(norm_cfg, planes)[1]
        self.downsample = downsample

    def forward(self, x):
        identity = x
        out = self.conv1(x)
        out = replace_feature(out, self.bn1(out.features))
        out = replace_feature(out, self.relu(out.features))
        out = self.conv2(out)
        out = replace_feature(out, self.bn2(out.features))
        if self.downsample is not None:
            identity = self.downsample(x)
        out = replace_feature(out, out.features + identity.features)
        out = replace_feature(out, self.relu(out.features))
        return out


# ---------------------------------------------------------------------------
#  LION window-mapping utilities
# ---------------------------------------------------------------------------
@torch.inference_mode()
def get_window_coors_shift_v2(coords, sparse_shape, window_shape, shift=False):
    sparse_shape_z, sparse_shape_y, sparse_shape_x = sparse_shape
    win_shape_x, win_shape_y, win_shape_z = window_shape

    if shift:
        shift_x, shift_y, shift_z = win_shape_x // 2, win_shape_y // 2, win_shape_z // 2
    else:
        shift_x, shift_y, shift_z = 0, 0, 0

    max_num_win_x = int(np.ceil(sparse_shape_x / win_shape_x) + 1)
    max_num_win_y = int(np.ceil(sparse_shape_y / win_shape_y) + 1)
    max_num_win_z = int(np.ceil(sparse_shape_z / win_shape_z) + 1)
    max_num_win_per_sample = max_num_win_x * max_num_win_y * max_num_win_z

    x = coords[:, 3] + shift_x
    y = coords[:, 2] + shift_y
    z = coords[:, 1] + shift_z

    win_coors_x = x // win_shape_x
    win_coors_y = y // win_shape_y
    win_coors_z = z // win_shape_z
    coors_in_win_x = x % win_shape_x
    coors_in_win_y = y % win_shape_y
    coors_in_win_z = z % win_shape_z

    batch_win_inds_x = (coords[:, 0] * max_num_win_per_sample
                        + win_coors_x * max_num_win_y * max_num_win_z
                        + win_coors_y * max_num_win_z + win_coors_z)
    batch_win_inds_y = (coords[:, 0] * max_num_win_per_sample
                        + win_coors_y * max_num_win_x * max_num_win_z
                        + win_coors_x * max_num_win_z + win_coors_z)

    coors_in_win = torch.stack([coors_in_win_z, coors_in_win_y, coors_in_win_x], dim=-1)
    return batch_win_inds_x, batch_win_inds_y, coors_in_win


def get_window_coors_shift_v1(coords, sparse_shape, window_shape):
    _, m, n = sparse_shape
    n2, m2, _ = window_shape
    n1 = int(np.ceil(n / n2) + 1)
    m1 = int(np.ceil(m / m2) + 1)
    x = coords[:, 3]
    y = coords[:, 2]
    x1 = x // n2
    y1 = y // m2
    x2 = x % n2
    y2 = y % m2
    return 2 * n2, 2 * m2, 2 * n1, 2 * m1, x1, y1, x2, y2


# ---------------------------------------------------------------------------
#  LION core modules
# ---------------------------------------------------------------------------
class FlattenedWindowMapping(nn.Module):
    def __init__(self, window_shape, group_size, shift, win_version="v2"):
        super().__init__()
        self.window_shape = window_shape
        self.group_size = group_size
        self.win_version = win_version
        self.shift = shift

    def forward(self, coords: torch.Tensor, batch_size: int, sparse_shape: list):
        coords = coords.long()
        _, num_per_batch = torch.unique(coords[:, 0], sorted=False, return_counts=True)
        batch_start_indices = F.pad(torch.cumsum(num_per_batch, dim=0), (1, 0))
        num_per_batch_p = (
            torch.div(
                batch_start_indices[1:] - batch_start_indices[:-1] + self.group_size - 1,
                self.group_size, rounding_mode="trunc",
            ) * self.group_size
        )
        batch_start_indices_p = F.pad(torch.cumsum(num_per_batch_p, dim=0), (1, 0))
        flat2win = torch.arange(batch_start_indices_p[-1], device=coords.device)
        win2flat = torch.arange(batch_start_indices[-1], device=coords.device)

        actual_batches = len(num_per_batch)
        for i in range(actual_batches):
            if num_per_batch[i] != num_per_batch_p[i]:
                bias_index = batch_start_indices_p[i] - batch_start_indices[i]
                flat2win[
                    batch_start_indices_p[i + 1] - self.group_size + (num_per_batch[i] % self.group_size):
                    batch_start_indices_p[i + 1]
                ] = flat2win[
                    batch_start_indices_p[i + 1]
                    - 2 * self.group_size
                    + (num_per_batch[i] % self.group_size): batch_start_indices_p[i + 1] - self.group_size
                ] if (batch_start_indices_p[i + 1] - batch_start_indices_p[i]) - self.group_size != 0 else \
                    win2flat[batch_start_indices[i]: batch_start_indices[i + 1]].repeat(
                        (batch_start_indices_p[i + 1] - batch_start_indices_p[i]) // num_per_batch[i] + 1)[
                    : self.group_size - (num_per_batch[i] % self.group_size)] + bias_index

            win2flat[batch_start_indices[i]: batch_start_indices[i + 1]] += (
                batch_start_indices_p[i] - batch_start_indices[i]
            )
            flat2win[batch_start_indices_p[i]: batch_start_indices_p[i + 1]] -= (
                batch_start_indices_p[i] - batch_start_indices[i]
            )

        mappings = {"flat2win": flat2win, "win2flat": win2flat}

        if self.win_version == "v1":
            for shifted in [False]:
                (n2, m2, n1, m1, x1, y1, x2, y2) = get_window_coors_shift_v1(
                    coords, sparse_shape, self.window_shape)
                vx = ((n1 * y1 + (-1) ** y1 * x1) * n2 * m2
                      + (-1) ** y1 * (m2 * x2 + (-1) ** x2 * y2))
                vx += coords[:, 0] * sparse_shape[2] * sparse_shape[1] * sparse_shape[0]
                vy = ((m1 * x1 + (-1) ** x1 * y1) * m2 * n2
                      + (-1) ** x1 * (n2 * y2 + (-1) ** y2 * x2))
                vy += coords[:, 0] * sparse_shape[2] * sparse_shape[1] * sparse_shape[0]
                _, mappings["x" + ("_shift" if shifted else "")] = torch.sort(vx)
                _, mappings["y" + ("_shift" if shifted else "")] = torch.sort(vy)

        elif self.win_version == "v2":
            bwi_x, bwi_y, ciw = get_window_coors_shift_v2(
                coords, sparse_shape, self.window_shape, self.shift)
            ws = self.window_shape
            vx = bwi_x * ws[0] * ws[1] * ws[2]
            vx += ciw[..., 2] * ws[1] * ws[2] + ciw[..., 1] * ws[2] + ciw[..., 0]
            vy = bwi_y * ws[0] * ws[1] * ws[2]
            vy += ciw[..., 1] * ws[0] * ws[2] + ciw[..., 2] * ws[2] + ciw[..., 0]
            _, mappings["x"] = torch.sort(vx)
            _, mappings["y"] = torch.sort(vy)

        return mappings


class PatchMerging3D(nn.Module):
    def __init__(self, dim, out_dim=-1, down_scale=None, norm_layer=nn.LayerNorm,
                 diffusion=False, diff_scale=0.2):
        super().__init__()
        if down_scale is None:
            down_scale = [2, 2, 2]
        self.dim = dim
        self.sub_conv = spconv.SparseSequential(
            SubMConv3d(dim, dim, 3, bias=False, indice_key="subm"),
            nn.LayerNorm(dim),
            nn.GELU(),
        )
        self.norm = norm_layer(dim if out_dim == -1 else out_dim)
        self.sigmoid = nn.Sigmoid()
        self.down_scale = down_scale
        self.diffusion = diffusion
        self.diff_scale = diff_scale

    def forward(self, x, coords_shift=1, diffusion_scale=4):
        assert diffusion_scale in (2, 4)
        x = self.sub_conv(x)
        d, h, w = x.spatial_shape
        down_scale = self.down_scale

        if self.diffusion:
            x_feat_att = x.features.mean(-1)
            batch_size = x.indices[:, 0].max() + 1
            sel_feats_list = [x.features.clone()]
            sel_coords_list = [x.indices.clone()]
            for i in range(batch_size):
                mask = x.indices[:, 0] == i
                valid_num = mask.sum()
                K = int(valid_num * self.diff_scale)
                _, top_idx = torch.topk(x_feat_att[mask], K)

                sc = x.indices[mask][top_idx].clone()
                sn = sc.shape[0]
                sc_exp = sc.repeat(diffusion_scale, 1)
                sf_exp = x.features[mask][top_idx].repeat(diffusion_scale, 1) * 0.0

                sc_exp[0:sn, 3:4] = (sc[:, 3:4] - coords_shift).clamp(0, w - 1)
                sc_exp[0:sn, 2:3] = (sc[:, 2:3] + coords_shift).clamp(0, h - 1)
                sc_exp[0:sn, 1:2] = sc[:, 1:2].clamp(0, d - 1)

                sc_exp[sn:2 * sn, 3:4] = (sc[:, 3:4] + coords_shift).clamp(0, w - 1)
                sc_exp[sn:2 * sn, 2:3] = (sc[:, 2:3] + coords_shift).clamp(0, h - 1)
                sc_exp[sn:2 * sn, 1:2] = sc[:, 1:2].clamp(0, d - 1)

                if diffusion_scale == 4:
                    sc_exp[2 * sn:3 * sn, 3:4] = (sc[:, 3:4] - coords_shift).clamp(0, w - 1)
                    sc_exp[2 * sn:3 * sn, 2:3] = (sc[:, 2:3] - coords_shift).clamp(0, h - 1)
                    sc_exp[2 * sn:3 * sn, 1:2] = sc[:, 1:2].clamp(0, d - 1)
                    sc_exp[3 * sn:4 * sn, 3:4] = (sc[:, 3:4] + coords_shift).clamp(0, w - 1)
                    sc_exp[3 * sn:4 * sn, 2:3] = (sc[:, 2:3] - coords_shift).clamp(0, h - 1)
                    sc_exp[3 * sn:4 * sn, 1:2] = sc[:, 1:2].clamp(0, d - 1)

                sel_coords_list.append(sc_exp)
                sel_feats_list.append(sf_exp)

            coords = torch.cat(sel_coords_list)
            final_feats = torch.cat(sel_feats_list)
        else:
            coords = x.indices.clone()
            final_feats = x.features.clone()

        coords[:, 3:4] = coords[:, 3:4] // down_scale[0]
        coords[:, 2:3] = coords[:, 2:3] // down_scale[1]
        coords[:, 1:2] = coords[:, 1:2] // down_scale[2]

        scale_xyz = ((x.spatial_shape[0] // down_scale[2])
                     * (x.spatial_shape[1] // down_scale[1])
                     * (x.spatial_shape[2] // down_scale[0]))
        scale_yz = (x.spatial_shape[0] // down_scale[2]) * (x.spatial_shape[1] // down_scale[1])
        scale_z = x.spatial_shape[0] // down_scale[2]

        merge_coords = (coords[:, 0].int() * scale_xyz
                        + coords[:, 3] * scale_yz
                        + coords[:, 2] * scale_z
                        + coords[:, 1])

        new_sparse_shape = [
            math.ceil(x.spatial_shape[i] / down_scale[2 - i]) for i in range(3)
        ]
        unq_coords, unq_inv = torch.unique(merge_coords, return_inverse=True,
                                            return_counts=False, dim=0)

        x_merge = scatter_sum(final_feats, unq_inv, dim=0)

        unq_coords = unq_coords.int()
        voxel_coords = torch.stack((
            unq_coords // scale_xyz,
            (unq_coords % scale_xyz) // scale_yz,
            (unq_coords % scale_yz) // scale_z,
            unq_coords % scale_z,
        ), dim=1)
        voxel_coords = voxel_coords[:, [0, 3, 2, 1]]

        x_merge = self.norm(x_merge)
        x_merge = spconv.SparseConvTensor(
            features=x_merge,
            indices=voxel_coords.int(),
            spatial_shape=new_sparse_shape,
            batch_size=x.batch_size,
        )
        return x_merge, unq_inv


class PatchExpanding3D(nn.Module):
    def __init__(self, dim):
        super().__init__()
        self.dim = dim

    def forward(self, x, up_x, unq_inv):
        n, c = x.features.shape
        x_copy = torch.gather(x.features, 0, unq_inv.unsqueeze(1).repeat(1, c))
        up_x = up_x.replace_feature(up_x.features + x_copy)
        return up_x


class PositionEmbeddingLearned(nn.Module):
    def __init__(self, input_channel, num_pos_feats):
        super().__init__()
        self.position_embedding_head = nn.Sequential(
            nn.Linear(input_channel, num_pos_feats),
            nn.BatchNorm1d(num_pos_feats),
            nn.ReLU(inplace=True),
            nn.Linear(num_pos_feats, num_pos_feats),
        )

    def forward(self, xyz):
        return self.position_embedding_head(xyz)


class LIONLayer(nn.Module):
    def __init__(self, dim, nums, window_shape, group_size, direction, shift,
                 operator=None, layer_id=0, n_layer=0):
        super().__init__()
        self.window_shape = window_shape
        self.group_size = group_size
        self.dim = dim
        self.direction = direction

        operator_cfg = dict(operator.CFG)
        operator_cfg["d_model"] = dim

        block_list = []
        for i in range(len(direction)):
            operator_cfg["layer_id"] = i + layer_id
            operator_cfg["n_layer"] = n_layer
            operator_cfg["with_cp"] = layer_id >= 0
            block_list.append(LinearOperatorMap[operator.NAME](**operator_cfg))

        self.blocks = nn.ModuleList(block_list)
        self.window_partition = FlattenedWindowMapping(
            self.window_shape, self.group_size, shift)

    def forward(self, x):
        mappings = self.window_partition(x.indices, x.batch_size, x.spatial_shape)

        for i, block in enumerate(self.blocks):
            indices = mappings[self.direction[i]]
            x_features = x.features[indices][mappings["flat2win"]]
            x_features = x_features.view(-1, self.group_size, x.features.shape[-1])
            x_features = block(x_features)
            x.features[indices] = x_features.view(-1, x_features.shape[-1])[mappings["win2flat"]]

        return x


class LIONBlock(nn.Module):
    def __init__(self, dim, depth, down_scales, window_shape, group_size,
                 direction, shift=False, operator=None, layer_id=0, n_layer=0):
        super().__init__()
        self.down_scales = down_scales

        self.encoder = nn.ModuleList()
        self.downsample_list = nn.ModuleList()
        self.pos_emb_list = nn.ModuleList()
        norm_fn = partial(nn.LayerNorm)

        shift_flags = [False, shift]
        for idx in range(depth):
            self.encoder.append(LIONLayer(
                dim, 1, window_shape, group_size, direction,
                shift_flags[idx], operator, layer_id + idx * 2, n_layer))
            self.pos_emb_list.append(
                PositionEmbeddingLearned(input_channel=3, num_pos_feats=dim))
            self.downsample_list.append(PatchMerging3D(
                dim, dim, down_scale=down_scales[idx], norm_layer=norm_fn))

        self.decoder = nn.ModuleList()
        self.decoder_norm = nn.ModuleList()
        self.upsample_list = nn.ModuleList()
        for idx in range(depth):
            self.decoder.append(LIONLayer(
                dim, 1, window_shape, group_size, direction,
                shift_flags[idx], operator, layer_id + 2 * (idx + depth), n_layer))
            self.decoder_norm.append(norm_fn(dim))
            self.upsample_list.append(PatchExpanding3D(dim))

    def forward(self, x):
        features, index = [], []
        for idx, enc in enumerate(self.encoder):
            pos_emb = self._get_pos_embed(
                x.spatial_shape, x.indices[:, 1:], self.pos_emb_list[idx])
            x = replace_feature(x, pos_emb + x.features)
            x = enc(x)
            features.append(x)
            x, unq_inv = self.downsample_list[idx](x)
            index.append(unq_inv)

        i = 0
        for dec, norm, up_x, unq_inv, _ in zip(
                self.decoder, self.decoder_norm,
                features[::-1], index[::-1], self.down_scales[::-1]):
            x = dec(x)
            x = self.upsample_list[i](x, up_x, unq_inv)
            x = replace_feature(x, norm(x.features))
            i += 1
        return x

    @staticmethod
    def _get_pos_embed(spatial_shape, coors, embed_layer, normalize_pos=True):
        window_shape = spatial_shape[::-1]  # ZYX -> XYZ
        if len(window_shape) == 2:
            win_x, win_y = window_shape
            win_z = 1
        else:
            win_x, win_y, win_z = window_shape
            if win_z == 0:
                win_z = 1

        z = coors[:, 0].float() - win_z / 2
        y = coors[:, 1].float() - win_y / 2
        x = coors[:, 2].float() - win_x / 2

        if normalize_pos:
            x = x / max(win_x, 1) * 2 * 3.1415
            y = y / max(win_y, 1) * 2 * 3.1415
            z = z / max(win_z, 1) * 2 * 3.1415

        location = torch.stack((x, y, z), dim=-1)
        return embed_layer(location)


# ---------------------------------------------------------------------------
#  Main backbone: SpConv stem + LION body
# ---------------------------------------------------------------------------
@BACKBONES.register_module
class LIONBackboneCenterPoint(nn.Module):
    """
    Hybrid SpConv-stem + LION-body backbone for CenterPoint.

    SpConv stem (conv_input → conv1 → conv2 → conv3) downsamples from the
    fine 0.075-voxel grid [41, 1440, 1440] to [11, 360, 360] with 64-ch.
    A linear transition projects 64 → feature_dim (128).

    LION body (4 LIONBlocks + inter-block Z-downsampling) processes the
    features with windowed Mamba/SSM operators, reducing Z to 1.

    A final stride-2 XY conv brings the BEV to 180×180, matching the
    original SpMiddleResNetFHD output resolution.

    Forward signature matches SpMiddleResNetFHD:
        forward(voxel_features, coors, batch_size, input_shape)
        → (dense_bev, multi_scale_voxel_features)
    """

    def __init__(
        self,
        num_input_features=5,
        ds_factor=8,
        # LION hyper-parameters
        feature_dim=128,
        layer_dim=None,
        num_layers=4,
        depths=None,
        layer_down_scales=None,
        window_shape=None,
        group_size=None,
        direction=None,
        diff_scale=0.2,
        diffusion=True,
        shift=True,
        operator_name="Mamba",
        operator_cfg=None,
        # misc
        norm_cfg=None,
        name="LIONBackboneCenterPoint",
        **kwargs,
    ):
        super().__init__()
        self.name = name

        if layer_dim is None:
            layer_dim = [128, 128, 128, 128]
        if depths is None:
            depths = [2, 2, 2, 2]
        if layer_down_scales is None:
            layer_down_scales = [[[2, 2, 2], [2, 2, 2]]] * 4
        if window_shape is None:
            window_shape = [[13, 13, 11], [13, 13, 6], [13, 13, 3], [13, 13, 2]]
        if group_size is None:
            group_size = [4096, 2048, 1024, 512]
        if direction is None:
            direction = ["x", "y"]
        if operator_cfg is None:
            operator_cfg = dict(d_state=16, d_conv=4, expand=2, drop_path=0.2)
        if norm_cfg is None:
            norm_cfg = dict(type="BN1d", eps=1e-3, momentum=0.01)

        assert operator_name in LinearOperatorMap, (
            f"Operator '{operator_name}' not available. "
            f"Installed: {list(LinearOperatorMap.keys())}"
        )
        assert num_layers == len(depths)

        operator = SimpleNamespace(NAME=operator_name, CFG=dict(operator_cfg))
        norm_fn = partial(nn.LayerNorm)
        n_layer = len(depths) * depths[0] * 2 * 2 + 2

        # ---- SpConv Stem (reused from SpMiddleResNetFHD) -------------------
        self.conv_input = spconv.SparseSequential(
            SubMConv3d(num_input_features, 16, 3, bias=False, indice_key="res0"),
            build_norm_layer(norm_cfg, 16)[1],
            nn.ReLU(inplace=True),
        )
        self.conv1 = spconv.SparseSequential(
            _SparseBasicBlock(16, 16, norm_cfg=norm_cfg, indice_key="res0"),
            _SparseBasicBlock(16, 16, norm_cfg=norm_cfg, indice_key="res0"),
        )
        self.conv2 = spconv.SparseSequential(
            SparseConv3d(16, 32, 3, 2, padding=1, bias=False),
            build_norm_layer(norm_cfg, 32)[1],
            nn.ReLU(inplace=True),
            _SparseBasicBlock(32, 32, norm_cfg=norm_cfg, indice_key="res1"),
            _SparseBasicBlock(32, 32, norm_cfg=norm_cfg, indice_key="res1"),
        )
        self.conv3 = spconv.SparseSequential(
            SparseConv3d(32, 64, 3, 2, padding=1, bias=False),
            build_norm_layer(norm_cfg, 64)[1],
            nn.ReLU(inplace=True),
            _SparseBasicBlock(64, 64, norm_cfg=norm_cfg, indice_key="res2"),
            _SparseBasicBlock(64, 64, norm_cfg=norm_cfg, indice_key="res2"),
        )

        # ---- Transition: SpConv channels → LION feature_dim ---------------
        self.transition = nn.Sequential(
            nn.Linear(64, feature_dim),
            nn.LayerNorm(feature_dim),
            nn.GELU(),
        )

        # ---- LION Body (4 blocks + inter-block Z-downsample) --------------
        self.linear_1 = LIONBlock(
            layer_dim[0], depths[0], layer_down_scales[0], window_shape[0],
            group_size[0], direction, shift=shift, operator=operator,
            layer_id=0, n_layer=n_layer)
        self.dow1 = PatchMerging3D(
            layer_dim[0], layer_dim[0], down_scale=[1, 1, 2],
            norm_layer=norm_fn, diffusion=diffusion, diff_scale=diff_scale)

        self.linear_2 = LIONBlock(
            layer_dim[1], depths[1], layer_down_scales[1], window_shape[1],
            group_size[1], direction, shift=shift, operator=operator,
            layer_id=8, n_layer=n_layer)
        self.dow2 = PatchMerging3D(
            layer_dim[1], layer_dim[1], down_scale=[1, 1, 2],
            norm_layer=norm_fn, diffusion=diffusion, diff_scale=diff_scale)

        self.linear_3 = LIONBlock(
            layer_dim[2], depths[2], layer_down_scales[2], window_shape[2],
            group_size[2], direction, shift=shift, operator=operator,
            layer_id=16, n_layer=n_layer)
        self.dow3 = PatchMerging3D(
            layer_dim[2], layer_dim[3], down_scale=[1, 1, 2],
            norm_layer=norm_fn, diffusion=diffusion, diff_scale=diff_scale)

        self.linear_4 = LIONBlock(
            layer_dim[3], depths[3], layer_down_scales[3], window_shape[3],
            group_size[3], direction, shift=shift, operator=operator,
            layer_id=24, n_layer=n_layer)
        self.dow4 = PatchMerging3D(
            layer_dim[3], layer_dim[3], down_scale=[1, 1, 2],
            norm_layer=norm_fn, diffusion=diffusion, diff_scale=diff_scale)

        self.linear_out = LIONLayer(
            layer_dim[3], 1, [13, 13, 1], 256,
            direction=["x", "y"], shift=shift,
            operator=operator, layer_id=32, n_layer=n_layer)

        # ---- XY stride-2 conv to restore 180×180 resolution ---------------
        self.extra_conv = spconv.SparseSequential(
            SparseConv3d(feature_dim, feature_dim,
                         (1, 3, 3), (1, 2, 2), padding=(0, 1, 1), bias=False),
            build_norm_layer(norm_cfg, feature_dim)[1],
            nn.ReLU(),
        )

    # ------------------------------------------------------------------ #
    def forward(self, voxel_features, coors, batch_size, input_shape):
        # Build initial sparse tensor  (same as SpMiddleResNetFHD)
        sparse_shape = np.array(input_shape[::-1]) + [1, 0, 0]
        coors = coors.int()
        ret = spconv.SparseConvTensor(voxel_features, coors, sparse_shape, batch_size)

        # ---- SpConv stem ----
        x = self.conv_input(ret)
        x_conv1 = self.conv1(x)              # [41, 1440, 1440]
        x_conv2 = self.conv2(x_conv1)         # [21, 720, 720]
        x_conv3 = self.conv3(x_conv2)         # [11, 360, 360]

        # ---- Transition 64-ch → 128-ch ----
        x_lion = replace_feature(x_conv3, self.transition(x_conv3.features))

        # ---- LION body ----
        x = self.linear_1(x_lion)
        x1, _ = self.dow1(x)                  # Z: 11→6
        x = self.linear_2(x1)
        x2, _ = self.dow2(x)                  # Z: 6→3
        x = self.linear_3(x2)
        x3, _ = self.dow3(x)                  # Z: 3→2
        x = self.linear_4(x3)
        x4, _ = self.dow4(x)                  # Z: 2→1
        x = self.linear_out(x4)               # [1, 360, 360]

        # ---- Extra conv: XY stride 2 → [1, 180, 180] ----
        ret = self.extra_conv(x)

        # ---- Height compression: sparse → dense BEV ----
        ret = ret.dense()
        N, C, D, H, W = ret.shape
        ret = ret.view(N, C * D, H, W)        # (N, 128, 180, 180)

        multi_scale_voxel_features = {
            "conv1": x_conv1,
            "conv2": x_conv2,
            "conv3": x_conv3,
            "conv4": x4,
        }
        return ret, multi_scale_voxel_features
