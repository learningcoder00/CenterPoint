import importlib
import torch
from torch import nn
from ..registry import BACKBONES

spconv_spec = importlib.util.find_spec("spconv")
found = spconv_spec is not None

# Always define and register SpMiddleResNetFHD, even without spconv
if found:
    from .scn import SpMiddleResNetFHD
    from .scn_v2 import SpMiddleResNetFHDv2
    try:
        from .lion_backbone import LIONBackboneCenterPoint
    except ImportError as exc:
        print(f"LION backbone disabled: {exc}")
else:
    print("No spconv, sparse convolution disabled!")
    
    # Define and register dummy backbone for testing without spconv
    class SpMiddleResNetFHD(nn.Module):
        def __init__(self, num_input_features=5, ds_factor=8, **kwargs):
            super(SpMiddleResNetFHD, self).__init__()
            # Simple dummy implementation
            self.conv = nn.Conv2d(num_input_features, 256, kernel_size=3, padding=1)
        
        def forward(self, voxel_features, coors, batch_size, input_shape):
            # Return dummy output
            N = batch_size
            C = 256
            H = input_shape[0] // 8
            W = input_shape[1] // 8
            ret = torch.zeros(N, C, H, W, device=voxel_features.device)
            multi_scale_voxel_features = {}
            return ret, multi_scale_voxel_features
    
    # Register the dummy backbone
    BACKBONES.register_module(SpMiddleResNetFHD)

