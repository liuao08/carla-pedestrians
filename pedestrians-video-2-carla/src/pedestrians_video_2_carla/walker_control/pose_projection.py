import carla
import cameratransform as ct
import numpy as np
import cv2

from pedestrians_video_2_carla.walker_control.controlled_pedestrian import ControlledPedestrian
from pedestrians_video_2_carla.utils.setup import get_camera_transform


class RGBCameraMock(object):
    """
    Mocks up the default CARLA camera.
    """

    def __init__(self, pedestrian: ControlledPedestrian, x=800, y=600):
        super().__init__()

        self.attributes = {
            'image_size_x': str(x),
            'image_size_y': str(y),
            'fov': '90.0',
            'lens_x_size': '0.08',
            'lens_y_size': '0.08'
        }
        self._transform = get_camera_transform(pedestrian)

    def get_transform(self):
        return self._transform


class PoseProjection(object):
    def __init__(self, pedestrian: ControlledPedestrian, camera_rgb: carla.Sensor = None, *args, **kwargs) -> None:
        super().__init__()

        self._pedestrian = pedestrian

        if camera_rgb is None:
            camera_rgb = RGBCameraMock(pedestrian)

        self._image_size = (
            int(camera_rgb.attributes['image_size_x']),
            int(camera_rgb.attributes['image_size_y'])
        )
        self._camera_ct = self._setup_camera(camera_rgb)

    def _setup_camera(self, camera_rgb: carla.Sensor):
        # basic transform is in UE world coords, axes of which are different
        # additionally, we need to correct spawn shift error
        cam_y_offset = camera_rgb.get_transform().location.x - \
            self._pedestrian.world_transform.location.x + \
            self._pedestrian.spawn_shift.x
        cam_z_offset = camera_rgb.get_transform().location.z - \
            self._pedestrian.world_transform.location.z + \
            self._pedestrian.spawn_shift.z

        camera_ct = ct.Camera(
            ct.RectilinearProjection(
                image_width_px=self._image_size[0],
                image_height_px=self._image_size[1],
                view_x_deg=float(camera_rgb.attributes['fov']),
                sensor_width_mm=float(camera_rgb.attributes['lens_x_size'])*1000,
                sensor_height_mm=float(camera_rgb.attributes['lens_y_size'])*1000
            ),
            ct.SpatialOrientation(
                pos_y_m=cam_y_offset,
                elevation_m=cam_z_offset,
                heading_deg=180,
                tilt_deg=90
            )
        )

        return camera_ct

    def current_pose_to_points(self):
        # switch from UE world coords, axes of which are different
        ct_transform = carla.Transform(location=carla.Location(
            x=self._pedestrian.transform.location.y,
            y=self._pedestrian.transform.location.x,
            z=self._pedestrian.transform.location.z
        ), rotation=carla.Rotation(
            yaw=-self._pedestrian.transform.rotation.yaw
        ))

        relativeBones = [
            ct_transform.transform(carla.Location(
                x=-bone.location.x,
                y=bone.location.y,
                z=bone.location.z
            ))
            for bone in self._pedestrian.current_pose.absolute.values()
        ]
        return self._camera_ct.imageFromSpace([
            (bone.x, bone.y, bone.z)
            for bone in relativeBones
        ], hide_backpoints=False)

    def current_pose_to_image(self, frame_no):
        points = self.current_pose_to_points()
        rounded = np.round(points).astype(int)

        img = np.zeros((self._image_size[1], self._image_size[0], 4), np.uint8)
        for point in rounded:
            cv2.circle(img, point, 1, [0, 0, 255, 255], 1)

        cv2.line(img, rounded[0], rounded[1], [255, 0, 0, 255], 1)
        cv2.circle(img, rounded[1], 1, [0, 255, 0, 255], 3)

        cv2.imwrite(
            '/outputs/carla/{:06d}_pose.png'.format(frame_no), img)


if __name__ == "__main__":
    from queue import Queue, Empty
    from collections import OrderedDict

    from pedestrians_video_2_carla.utils.destroy import destroy
    from pedestrians_video_2_carla.utils.setup import *
    from pedestrians_video_2_carla.walker_control.controlled_pedestrian import ControlledPedestrian

    client, world = setup_client_and_world()
    pedestrian = ControlledPedestrian(world, 'adult', 'female')

    sensor_dict = OrderedDict()
    camera_queue = Queue()

    sensor_dict['camera_rgb'] = setup_camera(
        world, camera_queue, pedestrian
    )

    projection = PoseProjection(
        pedestrian,
        sensor_dict['camera_rgb']
    )

    ticks = 0
    while ticks < 10:
        w_frame = world.tick()

        try:
            sensor_data = camera_queue.get(True, 1.0)
            sensor_data.save_to_disk(
                '/outputs/carla/{:06d}.png'.format(sensor_data.frame))
            projection.current_pose_to_image(w_frame)
            ticks += 1
        except Empty:
            print("Some sensor information is missed in frame {:06d}".format(w_frame))

        # rotate & apply slight movement to pedestrian to see if projections are working correctly
        pedestrian.teleport_by(carla.Transform(
            rotation=carla.Rotation(
                yaw=15
            )
        ))
        pedestrian.update_pose({
            'crl_arm__L': carla.Rotation(yaw=-6),
            'crl_foreArm__L': carla.Rotation(pitch=-6)
        })

    destroy(client, world, sensor_dict)
