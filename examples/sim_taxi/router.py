#!/usr/bin/env python
# coding: utf-8

import eventlet
from sys import float_info
from flask import Flask, jsonify, render_template
from flask_cors import CORS
from flask_mqtt import Mqtt
from flask_socketio import SocketIO

from config.env import env
from ams import Waypoint, Arrow, Intersection, Topic
from ams.nodes import Vehicle, User, TrafficSignal, FleetManager
from ams.messages import fleet_manager_message

eventlet.monkey_patch()

app = Flask(__name__)
with app.app_context():
    app.arrow = Arrow()
    app.arrow.load("../../res/arrow.json")
    app.waypoint = Waypoint()
    app.waypoint.load("../../res/waypoint.json")
    app.intersection = Intersection()
    app.intersection.load("../../res/intersection.json")

CORS(app)

app.config['MQTT_BROKER_URL'] = env["MQTT_BROKER_HOST"]
app.config['MQTT_BROKER_PORT'] = int(env["MQTT_BROKER_PORT"])
# app.config['MQTT_KEEPALIVE'] = 5
# app.config['MQTT_TLS_ENABLED'] = False
mqtt = Mqtt(app)

app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)


def api_response(code=200, message=None):
    if message is None:
        response = jsonify({})
    else:
        response = jsonify(message)
    response.status_code = code
    return response


@app.route('/')
def root():
    mqtt.subscribe(User.TOPIC.PUBLISH+"/#")
    mqtt.subscribe(Vehicle.TOPIC.PUBLISH+"/#")
    mqtt.subscribe(TrafficSignal.TOPIC.PUBLISH+"/#")
    mqtt.subscribe(FleetManager.TOPIC.PUBLISH+"/#")
    print("socketio", socketio)
    return render_template("index.html", title="ams", name="test_name")


@app.route("/getViewData")
def get_view_data():
    waypoint_ids = app.waypoint.get_waypoint_ids()
    waypoints = {}
    arrows = app.arrow.get_arrows()
    lat_min, lng_min = float_info.max, float_info.max
    lat_max, lng_max = 0.0, 0.0
    for waypoint_id in waypoint_ids:
        lat, lng = app.waypoint.get_latlng(waypoint_id)
        lat_min = min(lat_min, lat)
        lat_max = max(lat_max, lat)
        lng_min = min(lng_min, lng)
        lng_max = max(lng_max, lng)
        waypoints[waypoint_id] = {
            "geohash": app.waypoint.get_geohash(waypoint_id),
            "position": dict(zip(["x", "y", "z"], app.waypoint.get_xyz(waypoint_id)))
        }
    return api_response(code=200, message={
        "viewPoint": {
            "lat": 0.5*(lat_max + lat_min),
            "lng": 0.5*(lng_max + lng_min)},
        "waypoints": waypoints,
        "arrows": arrows,
        "topics": {
            "user": User.TOPIC.PUBLISH,
            "vehicle": Vehicle.TOPIC.PUBLISH,
            "trafficSignal": TrafficSignal.TOPIC.PUBLISH,
            "fleetManager": FleetManager.TOPIC.PUBLISH
        }
    })


@app.route("/requestFleetRelations")
def request_fleet_relations():
    topic = Topic()
    topic.set_root(FleetManager.TOPIC.SUBSCRIBE)
    topic.set_message(fleet_manager_message)
    message = topic.get_template()
    message["action"] = FleetManager.ACTION.PUBLISH_RELATIONS
    mqtt.publish(topic.root, topic.serialize(message))
    return api_response(code=200, message={"result": "requested"})


@socketio.on('message')
def handle_message(message):
    print("handle_message", message)


@mqtt.on_topic(User.TOPIC.PUBLISH+"/#")
def handle_mqtt_ontopic_user_status(_client, _userdata, mqtt_message):
    message = mqtt_message.payload.decode("utf-8")
    socketio.emit(User.TOPIC.PUBLISH, data={"topic": mqtt_message.topic, "message": message}, namespace="/ams")


@mqtt.on_topic(Vehicle.TOPIC.PUBLISH+"/#")
def handle_mqtt_ontopic_vehicle_status(_client, _userdata, mqtt_message):
    message = mqtt_message.payload.decode("utf-8")
    socketio.emit(Vehicle.TOPIC.PUBLISH, data={"topic": mqtt_message.topic, "message": message}, namespace="/ams")


@mqtt.on_topic(TrafficSignal.TOPIC.PUBLISH+"/#")
def handle_mqtt_ontopic_traffic_signal_status(_client, _userdata, mqtt_message):
    message = mqtt_message.payload.decode("utf-8")
    socketio.emit(
        TrafficSignal.TOPIC.PUBLISH, data={"topic": mqtt_message.topic, "message": message}, namespace="/ams")


@mqtt.on_topic(FleetManager.TOPIC.PUBLISH+"/#")
def handle_mqtt_ontopic_fleet_status(_client, _userdata, mqtt_message):
    message = mqtt_message.payload.decode("utf-8")
    socketio.emit(
        FleetManager.TOPIC.PUBLISH, data={"topic": mqtt_message.topic, "message": message}, namespace="/ams")


if __name__ == '__main__':
    socketio.run(app, host=env["AMS_HOST"], port=int(env["AMS_PORT"]), use_reloader=True, debug=True)
