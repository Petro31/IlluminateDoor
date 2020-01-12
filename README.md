# Illuminate Door

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)
<br><a href="https://www.buymeacoffee.com/Petro31" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-black.png" width="150px" height="35px" alt="Buy Me A Coffee" style="height: 35px !important;width: 150px !important;" ></a>

Illuminate a door for a specified duration when the door is opened. 

## Installation

Download the `illuminate_door` directory from inside the `apps` directory here to your local `apps` directory, then add the configuration to enable the `hacs` module.

## Use Case Examples

It's the holiday season.  Your front door lights are set to holiday colors.  When the front door opens, your holiday colored lights will change to bright yellow for 2 minutes, then return to 

## Example App configuration

#### Basic
```yaml
front_door_illumination:
  module: illuminate_door
  class: IlluminateDoor
  sensor: sensor.front_door
  turn_on:
  - switch.foyer
```

#### Advanced
```yaml
front_door_illumination:
  module: illuminate_door
  class: IlluminateDoor
  sensor: sensor.front_door
  turn_on:
  - switch.foyer
  - entity: light.foyer
    data:
      brightness: 255
      rgb_color: [ 255, 255, 255 ]
  duration: 300
  sundown: false
  log_level: INFO
```

#### App Configuration
key | optional | type | default | description
-- | -- | -- | -- | --
`module` | False | string | illuminate_door | The module name of the app.
`class` | False | string | IlluminateDoor | The name of the Class.
`sensor` | False | string | | The entity_id of the door sensor.
`turn_on` | False | list | | A list of entity_id's or entity objects.
`duration` | True | int | 120 | Turn on light/switch duration in seconds.
`sundown` | True | bool | true | Uses sundown check.  If true, lights will only turn on after sundown.
`log_level` | True | `'INFO'` | `'DEBUG'` | `'DEBUG'` | Switches log level.  This for lazy debuggers.  If you don't want to restart appdaemon to view debug logs, change this to `'INFO'` and all debug logs for this app will show up in `'INFO'`.


#### Entity Object Configuration
key | optional | type | default | description
`entity` | False | string | | The entity_id of the switch or light.
`data` | True | map | | Turn on service data.  Whenever the door turns on a light or switch, this data will be passed to the service data.  Warning: Use only valid combinations.  Light combinations are not validated and can cause errors in Home Assistant.

## Notes
* The lights/switches will turn on when the door is opened.
* The door illumination duration starts after the door is closed.
* Subsequent open and closes will reset the duration.
* You can cancel any turn_on duration by turning_off the light/switch.
* Each light has a separate duration.
* If a light is already on and service data was provided, the app will store the state prior to the door opening and return to it after the duration.
