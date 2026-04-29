"""A stronger residualized sparse-conv backbone for CenterPoint.

`SpMiddleResNetFHDv2` is a drop-in replacement for `SpMiddleResNetFHD`:
it keeps the exact same I/O signature (same forward arguments, same
output dense tensor shape, same `multi_scale_voxel_features` keys,
same `ds_factor=8`), so the neck / head / assigner do NOT need any
change.  Compared with the baseline, it provides:

  * deeper, configurable stage depths (default [3, 3, 3, 3] instead of
    the baseline's [2, 2, 2, 2]);
  * a wider stem (stacked SubM 3x3 convs) for richer low-level features;
  * an extra SubM 3x3 right after every stride-2 `SparseConv3d`, which
    stabilizes the channel-/resolution-transition;
  * stochastic depth (DropPath) on the residual branch, linearly
    scheduled across all blocks, to regularize deeper networks;
  * optional zero-init of the last BN in each residual branch (ResNet
    zero-gamma trick) so the network starts as an identity mapping.

All of the above are switchable from the config, enabling controlled
ablations.
"""
import numpy as np

try:
    import spconv.pytorch as spconv
    from spconv.pytorch import SparseConv3d, SubMConv3d
except Exception:  # pragma: no cover - fallback to spconv 1.x
    import spconv
    from spconv import SparseConv3d, SubMConv3d

import torch
from torch import nn

from ..registry import BACKBONES
from ..utils import build_norm_layer
from .scn import replace_feature, conv3x3


class DropPath(nn.Module):
    """Per-sample stochastic depth applied on sparse features.

    Note: spconv `SparseConvTensor.features` is a ``[N_total_active, C]``
    dense tensor that pools *all* samples in the batch together.  Applying
    a per-sample mask on it is not straightforward because it would
    require the batch index of every active voxel.  For simplicity and
    speed, we apply a *per-voxel* Bernoulli mask, which in practice
    behaves like DropOut on the residual branch and still serves as an
    effective regularizer for deep sparse networks.
    """

    def __init__(self, drop_prob: float = 0.0):
        super().__init__()
        self.drop_prob = float(drop_prob)

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        if self.drop_prob <= 0.0 or not self.training:
            return features
        keep_prob = 1.0 - self.drop_prob
        mask = features.new_empty(features.shape[0], 1).bernoulli_(keep_prob)
        return features * mask / keep_prob


class SparseBasicBlockV2(spconv.SparseModule):
    """Post-activation residual block with optional stochastic depth.

    Mirrors ``scn.SparseBasicBlock`` but:
      * adds a ``drop_path`` branch on the residual;
      * optionally zero-inits the last BN (``zero_init_residual``) so
        each block starts as an identity, which stabilizes deeper nets.
    """

    expansion = 1

    def __init__(
        self,
        inplanes,
        planes,
        stride=1,
        norm_cfg=None,
        downsample=None,
        indice_key=None,
        drop_path=0.0,
        zero_init_residual=False,
    ):
        super().__init__()

        if norm_cfg is None:
            norm_cfg = dict(type="BN1d", eps=1e-3, momentum=0.01)
        bias = norm_cfg is not None

        self.conv1 = conv3x3(inplanes, planes, stride, indice_key=indice_key, bias=bias)
        self.bn1 = build_norm_layer(norm_cfg, planes)[1]
        self.relu = nn.ReLU()
        self.conv2 = conv3x3(planes, planes, indice_key=indice_key, bias=bias)
        self.bn2 = build_norm_layer(norm_cfg, planes)[1]
        self.downsample = downsample
        self.stride = stride
        self.drop_path = DropPath(drop_path)

        if zero_init_residual and hasattr(self.bn2, "weight") and self.bn2.weight is not None:
            nn.init.zeros_(self.bn2.weight)

    def forward(self, x):
        identity = x

        out = self.conv1(x)
        out = replace_feature(out, self.bn1(out.features))
        out = replace_feature(out, self.relu(out.features))

        out = self.conv2(out)
        out = replace_feature(out, self.bn2(out.features))

        if self.downsample is not None:
            identity = self.downsample(x)

        out = replace_feature(
            out, self.drop_path(out.features) + identity.features
        )
        out = replace_feature(out, self.relu(out.features))

        return out


@BACKBONES.register_module
class SpMiddleResNetFHDv2(nn.Module):
    """Deeper residualized sparse conv backbone.

    Interface is identical to :class:`SpMiddleResNetFHD`: call
    ``forward(voxel_features, coors, batch_size, input_shape)``, return
    ``(bev_dense_tensor, multi_scale_voxel_features_dict)``.

    Args:
        num_input_features: point feature dim (usually 5 on nuScenes).
        norm_cfg: norm config dict.
        layer_nums: number of residual blocks at each of the 4 stages.
            Default ``(3, 3, 3, 3)``; baseline is ``(2, 2, 2, 2)``.
        base_channels: output channels of the 4 stages.  Default
            ``(16, 32, 64, 128)`` matches the baseline so the neck /
            head do not need to change.  Setting e.g. ``(32, 64, 96, 128)``
            widens the early stages.
        stem_num_layers: number of SubM 3x3 convs at the input stem.
            Default ``2`` (baseline uses ``1``).
        transition_conv: if True, add an extra SubM 3x3 right after each
            stride-2 downsample ``SparseConv3d`` (default True).
        drop_path_rate: maximum stochastic-depth rate; actual per-block
            rate is linearly scheduled from 0 to this value.  Default 0.
        zero_init_residual: zero-init the last BN of each residual block
            (ResNet zero-gamma trick).  Default False.
        ds_factor: consumed by ``get_downsample_factor`` in the config
            tooling; kept for API compatibility.  Default 8.
    """

    def __init__(
        self,
        num_input_features=128,
        norm_cfg=None,
        name="SpMiddleResNetFHDv2",
        layer_nums=(3, 3, 3, 3),
        base_channels=(16, 32, 64, 128),
        stem_num_layers=2,
        transition_conv=True,
        drop_path_rate=0.0,
        zero_init_residual=False,
        ds_factor=8,
        **kwargs,
    ):
        super().__init__()
        self.name = name
        self.dcn = None
        self.zero_init_residual = zero_init_residual
        self.ds_factor = ds_factor

        if norm_cfg is None:
            norm_cfg = dict(type="BN1d", eps=1e-3, momentum=0.01)

        assert len(layer_nums) == 4, "layer_nums must have 4 elements (4 stages)"
        assert len(base_channels) == 4, "base_channels must have 4 elements"
        assert stem_num_layers >= 1

        c1, c2, c3, c4 = base_channels

        total_blocks = sum(layer_nums)
        if total_blocks > 1:
            dpr = [
                drop_path_rate * i / (total_blocks - 1) for i in range(total_blocks)
            ]
        else:
            dpr = [0.0] * total_blocks
        blk_idx = 0

        # -------------------------- stem --------------------------
        stem_layers = [
            SubMConv3d(num_input_features, c1, 3, bias=False, indice_key="res0"),
            build_norm_layer(norm_cfg, c1)[1],
            nn.ReLU(inplace=True),
        ]
        for _ in range(stem_num_layers - 1):
            stem_layers += [
                SubMConv3d(c1, c1, 3, bias=False, indice_key="res0"),
                build_norm_layer(norm_cfg, c1)[1],
                nn.ReLU(inplace=True),
            ]
        self.conv_input = spconv.SparseSequential(*stem_layers)

        # ------------------------ stage 1 ------------------------
        # no spatial downsample; channels stay c1
        s1 = []
        for _ in range(layer_nums[0]):
            s1.append(
                SparseBasicBlockV2(
                    c1, c1, norm_cfg=norm_cfg, indice_key="res0",
                    drop_path=dpr[blk_idx],
                    zero_init_residual=zero_init_residual,
                )
            )
            blk_idx += 1
        self.conv1 = spconv.SparseSequential(*s1)

        # ------------------------ stage 2 ------------------------
        # downsample x2 in all 3 dims
        self.conv2 = self._make_down_stage(
            c1, c2, num_blocks=layer_nums[1], indice_key="res1",
            padding=1, stride=2, transition_conv=transition_conv,
            norm_cfg=norm_cfg, dpr=dpr, blk_idx_start=blk_idx,
            zero_init_residual=zero_init_residual,
        )
        blk_idx += layer_nums[1]

        # ------------------------ stage 3 ------------------------
        self.conv3 = self._make_down_stage(
            c2, c3, num_blocks=layer_nums[2], indice_key="res2",
            padding=1, stride=2, transition_conv=transition_conv,
            norm_cfg=norm_cfg, dpr=dpr, blk_idx_start=blk_idx,
            zero_init_residual=zero_init_residual,
        )
        blk_idx += layer_nums[2]

        # ------------------------ stage 4 ------------------------
        # no padding on z dim (matches the baseline's [0, 1, 1])
        self.conv4 = self._make_down_stage(
            c3, c4, num_blocks=layer_nums[3], indice_key="res3",
            padding=[0, 1, 1], stride=2, transition_conv=transition_conv,
            norm_cfg=norm_cfg, dpr=dpr, blk_idx_start=blk_idx,
            zero_init_residual=zero_init_residual,
        )
        blk_idx += layer_nums[3]

        # --------------------- z-dim reduction ---------------------
        # keep the same extra_conv as the baseline so the output is
        # [N, c4*2, H/8, W/8], i.e. 256 channels by default.
        self.extra_conv = spconv.SparseSequential(
            SparseConv3d(c4, c4, (3, 1, 1), (2, 1, 1), bias=False),
            build_norm_layer(norm_cfg, c4)[1],
            nn.ReLU(),
        )

    @staticmethod
    def _make_down_stage(
        inp, out, num_blocks, indice_key, padding, stride,
        transition_conv, norm_cfg, dpr, blk_idx_start, zero_init_residual,
    ):
        layers = [
            SparseConv3d(inp, out, 3, stride, padding=padding, bias=False),
            build_norm_layer(norm_cfg, out)[1],
            nn.ReLU(inplace=True),
        ]
        if transition_conv:
            layers += [
                SubMConv3d(out, out, 3, bias=False, indice_key=indice_key),
                build_norm_layer(norm_cfg, out)[1],
                nn.ReLU(inplace=True),
            ]
        for i in range(num_blocks):
            layers.append(
                SparseBasicBlockV2(
                    out, out, norm_cfg=norm_cfg, indice_key=indice_key,
                    drop_path=dpr[blk_idx_start + i],
                    zero_init_residual=zero_init_residual,
                )
            )
        return spconv.SparseSequential(*layers)

    def forward(self, voxel_features, coors, batch_size, input_shape):
        sparse_shape = np.array(input_shape[::-1]) + [1, 0, 0]

        coors = coors.int()
        ret = spconv.SparseConvTensor(voxel_features, coors, sparse_shape, batch_size)

        x = self.conv_input(ret)

        x_conv1 = self.conv1(x)
        x_conv2 = self.conv2(x_conv1)
        x_conv3 = self.conv3(x_conv2)
        x_conv4 = self.conv4(x_conv3)

        ret = self.extra_conv(x_conv4)

        ret = ret.dense()
        N, C, D, H, W = ret.shape
        ret = ret.view(N, C * D, H, W)

        multi_scale_voxel_features = {
            "conv1": x_conv1,
            "conv2": x_conv2,
            "conv3": x_conv3,
            "conv4": x_conv4,
        }
        return ret, multi_scale_voxel_features
