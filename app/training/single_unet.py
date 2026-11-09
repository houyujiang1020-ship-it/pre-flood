"""Single-image U-Net forward path using the shape-compatible SiamUnet_diff modules."""
import types

import torch
import torch.nn.functional as F
from torch.nn.modules.padding import ReplicationPad2d


def _forward(self, image):
    x11 = self.do11(F.relu(self.bn11(self.conv11(image))))
    x12 = self.do12(F.relu(self.bn12(self.conv12(x11))))
    x1p = F.max_pool2d(x12, 2, 2)
    x21 = self.do21(F.relu(self.bn21(self.conv21(x1p))))
    x22 = self.do22(F.relu(self.bn22(self.conv22(x21))))
    x2p = F.max_pool2d(x22, 2, 2)
    x31 = self.do31(F.relu(self.bn31(self.conv31(x2p))))
    x32 = self.do32(F.relu(self.bn32(self.conv32(x31))))
    x33 = self.do33(F.relu(self.bn33(self.conv33(x32))))
    x3p = F.max_pool2d(x33, 2, 2)
    x41 = self.do41(F.relu(self.bn41(self.conv41(x3p))))
    x42 = self.do42(F.relu(self.bn42(self.conv42(x41))))
    x43 = self.do43(F.relu(self.bn43(self.conv43(x42))))
    x4p = F.max_pool2d(x43, 2, 2)

    x4d = self.upconv4(x4p)
    x4d = torch.cat((ReplicationPad2d((0, x43.size(3) - x4d.size(3),
                                      0, x43.size(2) - x4d.size(2)))(x4d), x43), 1)
    x43d = self.do43d(F.relu(self.bn43d(self.conv43d(x4d))))
    x42d = self.do42d(F.relu(self.bn42d(self.conv42d(x43d))))
    x41d = self.do41d(F.relu(self.bn41d(self.conv41d(x42d))))
    x3d = self.upconv3(x41d)
    x3d = torch.cat((ReplicationPad2d((0, x33.size(3) - x3d.size(3),
                                      0, x33.size(2) - x3d.size(2)))(x3d), x33), 1)
    x33d = self.do33d(F.relu(self.bn33d(self.conv33d(x3d))))
    x32d = self.do32d(F.relu(self.bn32d(self.conv32d(x33d))))
    x31d = self.do31d(F.relu(self.bn31d(self.conv31d(x32d))))
    x2d = self.upconv2(x31d)
    x2d = torch.cat((ReplicationPad2d((0, x22.size(3) - x2d.size(3),
                                      0, x22.size(2) - x2d.size(2)))(x2d), x22), 1)
    x22d = self.do22d(F.relu(self.bn22d(self.conv22d(x2d))))
    x21d = self.do21d(F.relu(self.bn21d(self.conv21d(x22d))))
    x1d = self.upconv1(x21d)
    x1d = torch.cat((ReplicationPad2d((0, x12.size(3) - x1d.size(3),
                                      0, x12.size(2) - x1d.size(2)))(x1d), x12), 1)
    return self.conv11d(self.do12d(F.relu(self.bn12d(self.conv12d(x1d)))))


def attach_single_image_forward(model):
    """Replace only the forward graph; parameter names and shapes remain checkpoint-compatible."""
    model.forward = types.MethodType(_forward, model)
    return model
