#!/usr/bin/env python3
"""Run INSIDE SITL: verify live position, VIO, fusion and optional simulated flight."""
import argparse
import time

import rclpy
from rclpy.qos import qos_profile_sensor_data
from px4_msgs.msg import EstimatorStatusFlags, VehicleLocalPosition, VehicleOdometry, VehicleStatus
from offboard_interfaces.srv import Navigate
from std_srvs.srv import Trigger


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timeout', type=float, default=120)
    parser.add_argument('--flight', action='store_true', help='Take off and land in the simulator')
    args = parser.parse_args()
    rclpy.init()
    node = rclpy.create_node('sitl_regression_check')
    state = {}
    subscriptions = []
    for key, topic, kind in (
        ('position', '/fmu/out/vehicle_local_position', VehicleLocalPosition),
        ('vio', '/fmu/in/vehicle_visual_odometry', VehicleOdometry),
        ('fusion', '/fmu/out/estimator_status_flags', EstimatorStatusFlags),
        ('status', '/fmu/out/vehicle_status', VehicleStatus),
    ):
        def receive(msg, key=key):
            state[key] = (msg, time.monotonic())
        subscriptions.append(node.create_subscription(kind, topic, receive, qos_profile_sensor_data))

    def wait_for(predicate, label, timeout=args.timeout):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)
            if predicate():
                print('PASS:', label, flush=True)
                return
        raise RuntimeError(f'{label}: timed out; received={list(state)}')

    def fresh(key):
        return key in state and time.monotonic() - state[key][1] < 3

    def ready():
        if not all(fresh(key) for key in ('position', 'vio', 'fusion')):
            return False
        position, _ = state['position']
        fusion, _ = state['fusion']
        return (position.xy_valid and position.z_valid and not position.dead_reckoning
                and fusion.cs_ev_pos and fusion.cs_ev_yaw and fusion.cs_rng_hgt and not fusion.cs_gps)

    def service(client, request):
        if not client.wait_for_service(timeout_sec=5):
            raise RuntimeError(f'Service unavailable: {client.srv_name}')
        future = client.call_async(request)
        rclpy.spin_until_future_complete(node, future, timeout_sec=20)
        response = future.result() if future.done() else None
        if response is None or not response.success:
            raise RuntimeError(f'Service failed: {response}')
        return response

    navigate = node.create_client(Navigate, '/navigate')
    land = node.create_client(Trigger, '/land')
    try:
        wait_for(lambda: fresh('vio'), 'visual odometry reaches PX4')
        wait_for(ready, 'valid position and GPS-to-ArUco handoff')
        if not (navigate.wait_for_service(timeout_sec=5) and land.wait_for_service(timeout_sec=5)):
            raise RuntimeError('Flight services unavailable')
        print('PASS: /navigate and /land available', flush=True)
        if args.flight:
            baseline = state['position'][0].z
            request = Navigate.Request()
            request.z, request.speed = 1.0, 0.2
            request.frame_id, request.auto_arm = 'body', True
            try:
                service(navigate, request)
                wait_for(lambda: fresh('position') and baseline - state['position'][0].z > 0.75,
                         'takeoff above 0.75 m')
            finally:
                # Even a failed takeoff test must request landing before leaving.
                service(land, Trigger.Request())
            wait_for(lambda: fresh('status') and fresh('position')
                     and state['status'][0].arming_state == VehicleStatus.ARMING_STATE_DISARMED
                     and abs(state['position'][0].z - baseline) < 0.3,
                     'landed near ground and disarmed')
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
