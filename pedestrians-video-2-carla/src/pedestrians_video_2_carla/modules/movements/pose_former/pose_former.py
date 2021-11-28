import torch
from pedestrians_video_2_carla.modules.base.movements import MovementsModel
from pedestrians_video_2_carla.modules.base.output_types import MovementsModelOutputType
from torch import nn
from pedestrians_video_2_carla.submodules.pose_former.model_poseformer import PoseTransformer as PoseFormerModel


class PoseFormer(MovementsModel):
    """
    Based on the [PoseFormer implementation](https://github.com/zczcwh/PoseFormer)
    from the following paper:

    ```bibtex
    @article{zheng2021poseformer,
    title={3D Human Pose Estimation with Spatial and Temporal Transformers},
    author={Zheng, Ce and Zhu, Sijie and Mendieta, Matias and Yang,
        Taojiannan and Chen, Chen and Ding, Zhengming},
    journal={Proceedings of the IEEE International Conference on Computer Vision (ICCV)},
    year={2021}
    }
    ```
    """

    def __init__(self,
                 clip_length: int = 30,
                 receptive_frames: int = 9,
                 single_joint_embeddings_size=32,
                 depth=4,
                 num_heads=8,
                 mlp_ratio=2,
                 qkv_bias=True,
                 qk_scale=None,
                 drop_rate=0,
                 attn_drop_rate=0,
                 drop_path_rate=0.2,
                 **kwargs):
        super().__init__(**kwargs)

        self.__input_nodes_len = len(self.input_nodes)
        self.__input_features = 2  # (x, y) points

        self.__output_nodes_len = len(self.output_nodes)
        self.__output_features = 3  # (x, y, z) joints points

        self.__clip_length = clip_length
        self.__receptive_frames = receptive_frames
        self.__outputs_shift = self.__receptive_frames // 2

        assert self.__input_nodes_len == self.__output_nodes_len

        self.pose_former = PoseFormerModel(
            num_frame=receptive_frames,
            num_joints=self.__input_nodes_len,
            in_chans=self.__input_features,
            embed_dim_ratio=single_joint_embeddings_size,
            depth=depth,
            num_heads=num_heads,
            mlp_ratio=mlp_ratio,
            qkv_bias=qkv_bias,
            qk_scale=qk_scale,
            drop_rate=drop_rate,
            attn_drop_rate=attn_drop_rate,
            drop_path_rate=drop_path_rate,
            norm_layer=None
        )

        self._hparams = {
            'receptive_frames': receptive_frames,
            'single_joint_embeddings_size': single_joint_embeddings_size,
            'depth': depth,
            'num_heads': num_heads,
            'mlp_ratio': mlp_ratio,
            'qkv_bias': qkv_bias,
            'qk_scale': qk_scale,
            'drop_rate': drop_rate,
            'attn_drop_rate': attn_drop_rate,
            'drop_path_rate': drop_path_rate,
        }

    @property
    def output_type(self) -> MovementsModelOutputType:
        return MovementsModelOutputType.absolute_loc

    @property
    def eval_slice(self):
        return slice(self.__outputs_shift, self.__clip_length - self.__receptive_frames + self.__outputs_shift + 1)

    def forward(self, x, *args, **kwargs):
        original_shape = x.shape
        outputs = torch.zeros(
            (*original_shape[:2], self.__output_nodes_len, self.__output_features), device=x.device)

        for i in range(self.__clip_length - self.__receptive_frames + 1):
            x_slice = x[:, i:i + self.__receptive_frames, :, :]
            outputs[:, i + self.__outputs_shift:i + self.__receptive_frames +
                    self.__outputs_shift, :] = self.pose_former(x_slice)

        return outputs

    def configure_optimizers(self):
        optimizer = torch.optim.AdamW(self.parameters(), lr=0.0004, weight_decay=0.1)
        lr_scheduler = torch.optim.lr_scheduler.ExponentialLR(optimizer, gamma=0.99)

        config = {
            'optimizer': optimizer,
            'lr_scheduler': lr_scheduler
        }

        return config
