# coding=utf-8
# author Etienne G.

import json
import traceback
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass, asdict

from paho.mqtt.publish import multiple, single

from grottconf import Conf

__version__ = "0.0.7-RC8"

"""A pluging for grott
This plugin allow to have autodiscovery of the device in HA

Should be able to support multiples inverters

Version 0.0.7
  - Corrected a bug when creating the configuration
  - Add QoS 1 to reduce the possibility of lost message.
  - Updated Total work time unit.
  - Add support for setting the retain flag
  - Add more configurations for measures

Config:
    - ha_mqtt_host (required): The host of the MQTT broker user by HA (often the IP of HA)
    - ha_mqtt_port (required): The port (the default is oftent 1883)
    - ha_mqtt_user (optional): The user use to connect to the broker (you can use your user)
    - ha_mqtt_password (optional): The password to connect to the mqtt broket (you can use your password)
    - ha_mqtt_retain (optional): Set the retain flag for the data message (default: False)

Return codes:
    - 0: Everything is OK
    - 1: Missing MQTT extvar configuration
    - 2: Error while publishing the measure value message
    - 3: MQTT connection error
    - 4: Error while creating last_push status key
    - 5: Refused to push a buffered message (prevent invalid stats, not en error)
    - 6: Error while configuring HA MQTT sensor devices
    - 7: Can't configure device for HA MQTT
"""


CONFIG_TOPIC = "homeassistant/{sensor_type}/grott/{device}_{attribut}/config"
STATE_TOPIC = "homeassistant/grott/{device}/state"


@dataclass
class BaseSensor:
    name: str
    icon: Optional[str] = None
    value_template: Optional[str] = None


@dataclass
class MeasurementSensor(BaseSensor):
    state_class: str = "measurement"
    device_class: Optional[str] = None


@dataclass
class PercentSensor(MeasurementSensor):
    unit_of_measurement: str = "%"


@dataclass
class VoltageSensor(MeasurementSensor):
    device_class: str = "voltage"
    unit_of_measurement: str = "V"


@dataclass
class CurrentSensor(MeasurementSensor):
    device_class: str = "current"
    unit_of_measurement: str = "A"


@dataclass
class PowerSensor(MeasurementSensor):
    device_class: str = "power"
    unit_of_measurement: str = "W"


@dataclass
class FrequencySensor(MeasurementSensor):
    device_class: str = "frequency"
    unit_of_measurement: str = "Hz"


@dataclass
class TemperatureSensor(MeasurementSensor):
    device_class: str = "temperature"
    unit_of_measurement: str = "°C"


@dataclass
class DurationSensor(MeasurementSensor):
    device_class: str = "duration"
    unit_of_measurement: str = "h"


@dataclass
class ApparentPower(MeasurementSensor):
    device_class: str = "apparent_power"
    unit_of_measurement: str = "VA"


@dataclass
class BatteryChargeSensor(MeasurementSensor):
    device_class: str = "battery"
    unit_of_measurement: str = "%"


@dataclass
class EnergySensor(MeasurementSensor):
    state_class: str = "total"
    device_class: str = "energy"
    unit_of_measurement: str = "kWh"


@dataclass
class IncreasingEnergySensor(MeasurementSensor):
    state_class: str = "total_increasing"
    device_class: str = "energy"
    unit_of_measurement: str = "kWh"


mapping = {
    "datalogserial": BaseSensor("Datalogger serial"),
    "pvserial": BaseSensor("serial"),
    "pv1voltage": VoltageSensor("PV1 Voltage"),
    "pv1current": CurrentSensor("PV1 Current"),
    "pv1watt": PowerSensor("PV1 Watt"),
    "pv2voltage": VoltageSensor("PV2 Voltage"),
    "pv2current": CurrentSensor("PV2 Current"),
    "pv2watt": PowerSensor("PV2 Watt"),
    "pv3voltage": VoltageSensor("PV3 Voltage"),
    "pv3current": CurrentSensor("PV3 Current"),
    "pv3watt": PowerSensor("PV3 Watt"),
    "pvpowerin": PowerSensor("PV Input (Actual)"),
    "pvpowerout": PowerSensor("PV Output (Actual)"),
    "pvfrequentie": FrequencySensor("Grid Frequency", icon="mdi:waveform"),
    "frequency": FrequencySensor("Grid Frequency", icon="mdi:waveform"),
    "line_freq": FrequencySensor("Grid Frequency", icon="mdi:waveform"),
    "outputfreq": FrequencySensor("Inverter output frequency", icon="mdi:waveform"),
    "outputvolt": VoltageSensor("Inverter output Voltage"),
    # Grid config
    "grid_volt": VoltageSensor("Grid Voltage"),
    "bus_volt": VoltageSensor("Bus Voltage"),
    "pvgridvoltage": VoltageSensor("Phase 1 voltage"),
    "pvgridvoltage2": VoltageSensor("Phase 2 voltage"),
    "pvgridvoltage3": VoltageSensor("Phase 3 voltage"),
    "pvgridcurrent": CurrentSensor("Phase 1 current"),
    "pvgridcurrent2": CurrentSensor("Phase 2 current"),
    "pvgridcurrent3": CurrentSensor("Phase 3 current"),
    "pvgridpower": PowerSensor("Phase 1 power"),
    "pvgridpower2": PowerSensor("Phase 2 power"),
    "pvgridpower3": PowerSensor("Phase 3 power"),
    # End grid
    "pvenergytoday": EnergySensor("Generated energy (Today)", icon="mdi:solar-power"),
    "epvtoday": EnergySensor("Solar energy today", icon="mdi:solar-power"),
    "epvToday": IncreasingEnergySensor("Solar energy today", icon="mdi:solar-power"),
    "epv1today": EnergySensor("Solar PV1 energy today", icon="mdi:solar-power"),
    "epv2today": EnergySensor("Solar PV2 energy today", icon="mdi:solar-power"),
    "pvenergytotal": IncreasingEnergySensor(
        "Generated energy (Total)", icon="mdi:solar-power"
    ),
    "epvtotal": IncreasingEnergySensor("Lifetime solar energy", icon="mdi:solar-power"),
    "epv1total": IncreasingEnergySensor(
        "Solar PV1 production (Total)", icon="mdi:solar-power"
    ),
    "epv1tot": IncreasingEnergySensor(
        "Solar PV1 production (Total)", icon="mdi:solar-power"
    ),
    "epv2total": IncreasingEnergySensor(
        "Solar PV2 production (Total)", icon="mdi:solar-power"
    ),
    "epv2tot": IncreasingEnergySensor(
        "Solar PV3 production (Total)", icon="mdi:solar-power"
    ),
    # For SPH compatiblity
    "epvTotal": IncreasingEnergySensor(
        "Generated PV energy (Total)", icon="mdi:solar-power"
    ),
    "pactouserr": PowerSensor("Import from grid", icon="mdi:transmission-tower-export"),
    "pactousertot": PowerSensor(
        "Import from grid total", icon="mdi:transmission-tower-export"
    ),
    "pactogridr": PowerSensor("Export to grid", icon="mdi:solar-power"),
    "pactogridtot": PowerSensor("Export to grid total", icon="mdi:solar-power"),
    "pvstatus": BaseSensor("State", icon="mdi:power-settings"),
    "totworktime": DurationSensor(
        "Working time",
        value_template="{{ value_json.totworktime| float / 7200 | round(2) }}",
    ),
    "pvtemperature": TemperatureSensor("Inverter temperature", icon="mdi:thermometer"),
    "pvipmtemperature": TemperatureSensor(
        "Intelligent Power Management temperature", icon="mdi:thermometer"
    ),
    "pvboottemperature": TemperatureSensor(
        "Inverter boost temperature", icon="mdi:thermometer"
    ),
    "pvboosttemp": TemperatureSensor(
        "Inverter boost temperature", icon="mdi:thermometer"
    ),
    # Energy
    "etogrid_tod": EnergySensor(
        "Export to grid today", icon="mdi:transmission-tower-import"
    ),
    "etogrid_tot": IncreasingEnergySensor(
        "Lifetime export to grid", icon="mdi:transmission-tower-import"
    ),
    "etouser_tod": EnergySensor(
        "Import from grid (Today)", icon="mdi:transmission-tower-export"
    ),
    "etouser_tot": IncreasingEnergySensor(
        "Import from grid (Total)", icon="mdi:transmission-tower-export"
    ),
    # Need to investigate
    "elocalload_tod": EnergySensor(
        "Load consumption today", icon="mdi:solar-power", unit_of_measurement="Wh"
    ),
    "elocalload_tot": IncreasingEnergySensor(
        "Lifetime load consumption", icon="mdi:solar-power", unit_of_measurement="Wh"
    ),
    "AC_InWatt": PowerSensor("Grid input power"),
    "AC_InVA": ApparentPower("Grid input apparent power"),
    "plocaloadr": PowerSensor(
        "Local load consumption", icon="mdi:transmission-tower-export"
    ),
    # extension data
    "grott_last_push": MeasurementSensor(
        "Grott last data push",
        device_class="timestamp",
        value_template="{{value_json.grott_last_push}}",
    ),
    "grott_last_measure": MeasurementSensor(
        "Grott last measure",
        device_class="timestamp",
        value_template="{{value_json.grott_last_measure}}",
    ),
    # batteries
    "eacharge_today": EnergySensor(
        "Battery charge from AC (Today)", icon="mdi:battery-arrow-up"
    ),
    "eacCharToday": EnergySensor(
        "Battery charge from grid today", icon="mdi:battery-arrow-up"
    ),
    "eacharge_total": IncreasingEnergySensor(
        "Battery charge from AC (Total)", icon="mdi:battery-arrow-up"
    ),
    "eacCharTotal": IncreasingEnergySensor(
        "Lifetime battery charge from grid", icon="mdi:battery-arrow-up"
    ),
    "eacDischarToday": EnergySensor(
        "Battery dischage today", icon="mdi:battery-arrow-down"
    ),
    "eacDischarTotal": IncreasingEnergySensor(
        "Lifetime battery discharge", icon="mdi:battery-arrow-down"
    ),
    "vbat": VoltageSensor("Battery voltage"),
    "SOC": BatteryChargeSensor(
        "Battery charge",
        icon="mdi:battery-charging-60",
        value_template="{{ value_json.SOC | int }}",
    ),
    "loadpercent": PercentSensor("Load percentage"),
    "batterySoc": BatteryChargeSensor("Battery charge", icon="mdi:battery-charging-60"),
    "bat_Volt": VoltageSensor("Battery voltage"),
    "ACDischarWatt": PowerSensor("Load power"),
    "ACDischarVA": ApparentPower("Load reactive power"),
    "BatDischarWatt": PowerSensor("Battery discharge power"),
    "BatWatt": PowerSensor("Battery discharge power"),
    "BatDischarVA": ApparentPower("Battery discharge reactive power"),
    # taken from register 1048 of RTU manual v1.20
    "batterytype": BaseSensor(
        "Battery type",
        icon="mdi:power-settings",
        value_template="{% if value_json.batterytype == '0' %}Lithium{% elif value_json.batterytype == '1' %}Lead-acid{% elif value_json.batterytype == '2' %}Other{% else %}Unknown{% endif %}",
    ),
    "p1charge1": PowerSensor("Battery charge power", icon="mdi:battery-arrow-up"),
    "eharge1_tod": EnergySensor("Battery charge (Today)", icon="mdi:battery-arrow-up"),
    "eharge1_tot": IncreasingEnergySensor(
        "Battery charge (Total)", icon="mdi:battery-arrow-up"
    ),
    "edischarge1_tod": EnergySensor(
        "Battery discharge (Today)", icon="mdi:battery-arrow-down"
    ),
    "edischarge1_tot": IncreasingEnergySensor(
        "Battery discharge (Total)", icon="mdi:battery-arrow-down"
    ),
    "ebatDischarToday": EnergySensor(
        "Battery discharged today", icon="mdi:battery-arrow-down"
    ),
    "ebatDischarTotal": IncreasingEnergySensor(
        "Lifetime battery discharged", icon="mdi:battery-arrow-down"
    ),
    "pdischarge1": EnergySensor("Battery discharging W", icon="mdi:battery-arrow-down"),
    "ACCharCurr": CurrentSensor("Battery charging current"),
    "acchr_watt": PowerSensor("Storage charging from grid"),
    "acchr_VA": ApparentPower("Storage charging from grid reactive power"),
    "battemp": TemperatureSensor("Battery temperature", icon="mdi:thermometer"),
    "invtemp": TemperatureSensor("Inverter temperature", icon="mdi:thermometer"),
    "dcdctemp": TemperatureSensor(
        "Battery charger temperature", icon="mdi:thermometer"
    ),
    "spbusvolt": VoltageSensor("BP bus voltage"),
    # faults
    "faultcode": BaseSensor(name="Fault code"),
    "systemfaultword1": BaseSensor(name="System fault register 1"),
    "systemfaultword2": BaseSensor(name="System fault register 2"),
    "systemfaultword3": BaseSensor(name="System fault register 3"),
    "systemfaultword4": BaseSensor(name="System fault register 4"),
    "systemfaultword5": BaseSensor(name="System fault register 5"),
    "systemfaultword6": BaseSensor(name="System fault register 6"),
    "systemfaultword7": BaseSensor(name="System fault register 7"),
    "faultBit": BaseSensor(name="Fault message"),
    "warningBit": BaseSensor(name="Warning message"),
    "faultValue": BaseSensor(name="Fault value"),
    "warningValue": BaseSensor(name="Warning value"),
    "isof": VoltageSensor("ISO fault", icon="mdi:alert"),
    "gfcif": CurrentSensor("GFCI fault", icon="mdi:alert"),
    "dcif": CurrentSensor("DCI fault", icon="mdi:alert"),
    "vpvfault": VoltageSensor("PV voltage fault", icon="mdi:alert"),
    "vacfault": VoltageSensor("AC voltage fault", icon="mdi:alert"),
    "facfault": FrequencySensor("AC frequency fault", icon="mdi:alert"),
    "tmpfault": TemperatureSensor("Temperature fault", icon="mdi:alert"),
    # PV
    "vpv1": VoltageSensor("PV1 voltage"),
    "vpv2": VoltageSensor("PV2 voltage"),
    "ppv1": PowerSensor("PV1 Wattage"),
    "ppv2": PowerSensor("PV2 Wattage"),
    "buck1curr": CurrentSensor("Buck1 current"),
    "buck2curr": CurrentSensor("Buck2 current"),
    "op_watt": PowerSensor("Inverter active power"),
    "op_va": ApparentPower("Inverter apparent power"),
    "Inv_Curr": CurrentSensor("Inverter current"),
    "OP_Curr": CurrentSensor("Inverter consumption current"),
}

MQTT_HOST_CONF_KEY = "ha_mqtt_host"
MQTT_PORT_CONF_KEY = "ha_mqtt_port"
MQTT_USERNAME_CONF_KEY = "ha_mqtt_user"
MQTT_PASSWORD_CONF_KEY = "ha_mqtt_password"
MQTT_RETAIN_CONF_KEY = "ha_mqtt_retain"
# JSON_CONFIG = "ha_config"


def to_dict(obj: BaseSensor) -> dict:
    """Convert a dataclass object to dict

    :param obj: The sensor object to convert
    :return: A dictionary representation of the object
    """
    dict_obj = asdict(obj)
    # Remove None values
    return {k: v for k, v in dict_obj.items() if v is not None}


def make_payload(
    conf: Conf, device: str, key: str, name: Optional[str] = None, unit: str = None
) -> dict:
    """Generate a MQTT payload for a sensor
    Use default values to create a sensor payload, then update with custom
    attributes if they exist. (e.g. unit_of_measurement/total increasing/etc.)

    :param conf: The configuration object, use to extract default divider
    :param device: Use the device name as part of the sensor name + device
    :param key: The key of the sensor sent by grott
    :param name: The name of the sensor, if you want something different
    :param unit: unit of measurement
    :return: A dictionary with the MQTT configuration payload
    """

    if name is None:
        name = key

    # Default configuration payload
    payload = {
        "name": "{device} {name}",
        "unique_id": f"grott_{device}_{key}",  # Generate a unique device ID
        "state_topic": f"homeassistant/grott/{device}/state",
        "device": {
            "identifiers": [device],  # Group under a device
            "name": device,
            "manufacturer": "GrowWatt",
        },
    }

    # If there's a custom mapping, add the new values
    if key in mapping:
        key_mapping = mapping[key]
        if isinstance(key_mapping, BaseSensor):
            # convert the mapping to a dict
            key_mapping = to_dict(key_mapping)
        payload.update(key_mapping)

    if not payload["name"].startswith("{device} "):
        # Prepend the {device} template, prevent repeating
        payload["name"] = "{device} " + payload["name"]

    # Generate the name of the key, with all the param available
    payload["name"] = payload["name"].format(device=device, name=name, key=key)
    # HA automatically group the sensor if the device name is prepended

    # Reuse the existing divide value if available and not existing
    # and apply it to the HA config
    layout = conf.recorddict[conf.layout]
    if "value_template" not in payload and key in layout:
        # From grottdata:207, default type is num, also process numx
        if layout[key].get("type", "num") in ("num", "numx"):
            # default divide is 1
            divider = layout[key].get("divide", "1")
            payload[
                "value_template"
            ] = "{{{{ value_json.{key} | float / {divide} }}}}".format(
                key=key,
                divide=divider,
            )

    # generate a default value template if not existing
    if "value_template" not in payload:
        payload["value_template"] = f"{{{{ value_json.{key} }}}}"

    return payload


class MqttStateHandler:
    __pv_config = {}
    client_name = "Grott - HA"

    @classmethod
    def is_configured(cls, serial: str):
        return cls.__pv_config.get(serial, False)

    @classmethod
    def set_configured(cls, serial: str):
        cls.__pv_config[serial] = True


def process_conf(conf: Conf):
    required_params = [
        MQTT_HOST_CONF_KEY,
        MQTT_PORT_CONF_KEY,
    ]
    if not all([param in conf.extvar for param in required_params]):
        print("Missing configuration for ha_mqtt")
        raise AttributeError

    if MQTT_USERNAME_CONF_KEY in conf.extvar:
        auth = {
            "username": conf.extvar[MQTT_USERNAME_CONF_KEY],
            "password": conf.extvar[MQTT_PASSWORD_CONF_KEY],
        }
    else:
        auth = None

    # Need to convert the port if passed as a string
    port = conf.extvar[MQTT_PORT_CONF_KEY]
    if isinstance(port, str):
        port = int(port)
    return {
        "client_id": MqttStateHandler.client_name,
        "auth": auth,
        "hostname": conf.extvar[MQTT_HOST_CONF_KEY],
        "port": port,
    }


def publish_single(conf: Conf, topic, payload, retain=False):
    conf = process_conf(conf)
    return single(topic, payload=payload, retain=retain, **conf)


def publish_multiple(conf: Conf, msgs):
    conf = process_conf(conf)
    return multiple(msgs, **conf)


def grottext(conf: Conf, data: str, jsonmsg: str):
    """Allow to push to HA MQTT bus, with auto discovery"""

    required_params = [
        MQTT_HOST_CONF_KEY,
        MQTT_PORT_CONF_KEY,
    ]
    if not all([param in conf.extvar for param in required_params]):
        print("Missing configuration for ha_mqtt")
        return 1

    # Need to decode the json string
    jsonmsg = json.loads(jsonmsg)

    if jsonmsg.get("buffered") == "yes":
        # Skip buffered message, HA don't support them
        if conf.verbose:
            print("\t - Grott HA - skipped buffered")
        return 5

    device_serial = jsonmsg["device"]
    values = jsonmsg["values"]

    # Send the last push in UTC with TZ
    dt = datetime.now(timezone.utc)
    # Add a new value to the existing values
    values["grott_last_push"] = dt.isoformat()

    # Layout can be undefined
    if not MqttStateHandler.is_configured(device_serial) and getattr(
        conf, "layout", None
    ):
        configs_payloads = []
        print(
            f"\tGrott HA {__version__} - creating {device_serial} config in HA, {len(values.keys())} to push"
        )
        for key in values.keys():
            # Generate a configuration payload
            payload = make_payload(conf, device_serial, key)
            if not payload:
                print(f"\t[Grott HA] {__version__} skipped key: {key}")
                continue

            try:
                topic = CONFIG_TOPIC.format(
                    sensor_type="sensor",
                    device=device_serial,
                    attribut=key,
                )
                configs_payloads.append(
                    {
                        "topic": topic,
                        "payload": json.dumps(payload),
                        "retain": True,
                        "qos": 1,
                    }
                )
            except Exception as e:
                print(
                    f"\t - [grott HA] {__version__} Exception while creating new sensor {key}: {e}"
                )
                return 6

        # Create a virtual last_push key to allow tracking when there was the last data transmission

        try:
            key = "grott_last_push"
            payload = make_payload(conf, device_serial, key, key)
            topic = CONFIG_TOPIC.format(
                sensor_type="sensor",
                device=device_serial,
                attribut=key,
            )
            configs_payloads.append(
                {
                    "topic": topic,
                    "payload": json.dumps(payload),
                    "retain": True,
                    "qos": 1,
                }
            )
        except Exception as e:
            print(
                f"\t - [grott HA] {__version__} Exception while creating new sensor last push: {e}"
            )
            return 4
        print(f"\tPushing {len(configs_payloads)} configurations payload to HA")
        publish_multiple(conf, configs_payloads)
        print("\tConfigurations pushed")
        # Now it's configured, no need to come back
        MqttStateHandler.set_configured(device_serial)

    if not MqttStateHandler.is_configured(device_serial):
        print(f"\t[Grott HA] {__version__} Can't configure device: {device_serial}")
        return 7

    # Push the values to the topic
    retain = conf.extvar.get(MQTT_RETAIN_CONF_KEY, False)
    try:
        publish_single(
            conf,
            STATE_TOPIC.format(device=device_serial),
            json.dumps(values),
            retain=retain,
        )
    except Exception as e:
        print("[HA ext] - Exception while publishing - {}".format(e))
        # Reset connection state in case of problem
        if conf.verbose:
            traceback.print_exc()
        return 2
    return 0


def test_generate_payload():
    "Test that an auto generated payload for MQTT configuration"

    class TestConf:
        recorddict = {
            "test": {
                "pvpowerout": {"value": 122, "length": 4, "type": "num", "divide": 10}
            }
        }
        layout = "test"

    payload = make_payload(TestConf(), "NCO7410", "pvpowerout", "pvpowerout")
    print(payload)
    # The default divider for pvpowerout is 10
    assert payload["value_template"] == "{{ value_json.pvpowerout | float / 10 }}"
    assert payload["name"] == "NCO7410 PV Output (Actual)"
    assert payload["unique_id"] == "grott_NCO7410_pvpowerout"
    assert payload["state_class"] == "measurement"
    assert payload["device_class"] == "power"
    assert payload["unit_of_measurement"] == "W"


def test_generate_payload_without_divider():
    "Test that an auto generated payload for MQTT configuration"

    class TestConf:
        recorddict = {
            "test": {
                "pvpowerout": {
                    "value": 122,
                    "length": 4,
                    "type": "num",
                }
            }
        }
        layout = "test"

    payload = make_payload(TestConf(), "NCO7410", "pvpowerout", "pvpowerout")
    print(payload)
    # The default divider for pvpowerout is 10
    assert payload["value_template"] == "{{ value_json.pvpowerout | float / 1 }}"
    assert payload["name"] == "NCO7410 PV Output (Actual)"
    assert payload["unique_id"] == "grott_NCO7410_pvpowerout"
    assert payload["state_class"] == "measurement"
    assert payload["device_class"] == "power"
    assert payload["unit_of_measurement"] == "W"
