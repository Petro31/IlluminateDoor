import appdaemon.plugins.hass.hassapi as hass
import voluptuous as vol
import time

CONF_MODULE = 'module'
CONF_CLASS = 'class'
CONF_SENSOR = 'sensor'
CONF_TURN_ON = 'turn_on'
CONF_ENTITY = 'entity'
CONF_DURATION = 'duration'
CONF_SUNDOWN = 'sundown'
CONF_LOG_LEVEL = 'log_level'
CONF_DATA = 'data'

SCHEDULE_OVERRIDE = 'schedule_override'
SCHEDULE_ENTITY = 'schedule_entity'

ALL = 'all'
ENTITY_ID = 'entity_id'
STATE = 'state'
ATTRIBUTES = 'attributes'

LOG_ERROR = 'ERROR'
LOG_DEBUG = 'DEBUG'
LOG_INFO = 'INFO'

STATE_OPEN = 'open'
STATE_CLOSED = 'closed'
STATE_ON = 'on'
STATE_OFF = 'off'

DOOR_OPEN_STATES = [ STATE_OPEN, STATE_ON ]
DOOR_CLOSED_STATES = [ STATE_CLOSED, STATE_OFF ]

DOMAIN_LIGHT = 'light'

ATTR_RGB_COLOR = "rgb_color"
ATTR_XY_COLOR = "xy_color"
ATTR_HS_COLOR = "hs_color"
ATTR_COLOR_TEMP = "color_temp"
ATTR_WHITE_VALUE = "white_value"
ATTR_BRIGHTNESS = "brightness"
ATTR_EFFECT = "effect"

LIGHT_ATTRIBUTES = [
    ATTR_RGB_COLOR,
    ATTR_WHITE_VALUE,
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ]

ENTITIES_SCHEMA = [
    vol.Any(
        str,
        { 
            vol.Required(CONF_ENTITY): str,
            vol.Optional(CONF_DATA): {str: vol.Any(int, str, bool, list, dict)},
        })]

APP_SCHEMA = vol.Schema({
    vol.Required(CONF_MODULE): str,
    vol.Required(CONF_CLASS): str,
    vol.Required(CONF_SENSOR): str,
    vol.Required(CONF_TURN_ON): ENTITIES_SCHEMA,
    vol.Optional(CONF_SUNDOWN, default=True): bool,
    vol.Optional(CONF_DURATION, default=120): vol.All(int, vol.Range(min=1)),
    vol.Optional(CONF_LOG_LEVEL, default=LOG_DEBUG): vol.Any(LOG_INFO, LOG_DEBUG),
    })

class IlluminateDoor(hass.Hass):
    def initialize(self):
        args = APP_SCHEMA(self.args)

        # Set Lazy Logging (to not have to restart appdaemon)
        self._level = args.get(CONF_LOG_LEVEL)
        self.log(args, level=self._level)

        # Required
        self.entity = args.get(CONF_SENSOR)
        self.entities = [ AppEntity(e) for e in args.get(CONF_TURN_ON) ]

        # Optional
        self.use_sun = args.get(CONF_SUNDOWN)
        self.duration = args.get(CONF_DURATION)

        self.overrides = []

        self.handles = {}
        self.timers = {}

        self._stored_states = {}

        self.handles[self.entity] = self.listen_state(self.track_door, entity = self.entity)

    def track_door(self, entity, attribute, old, new, kwargs):

        if not self.use_sun or (self.use_sun and self.sun_down()):

            # Door is opened

            if new in DOOR_OPEN_STATES:
                for e in self.entities:
                    if e.entity_id not in self.overrides:
                        # Cancel any timers for the current entity.
                        # This case is for when someone opens the door
                        #   shuts the door, and opens again without shutting. 
                        self.cancel_timer_handle(e.entity_id)

                        # Turn on the entity if it is off.
                        self.turn_on_if_off(e.entity_id, e.attributes)
    
                        # create a override door listen state handle for each entity
                        self.start_listen_state_handle(e.entity_id)
                        
                # cancel the override if the door is opened after closing and stays open.
                self.cancel_timer_handle(SCHEDULE_OVERRIDE)

            # Door is Closed

            if new in DOOR_CLOSED_STATES:
                for e in self.entities:
                    if e.entity_id not in self.overrides:
                        self.start_timer_handle(e.entity_id)

                # clear the overrides because all timers should have been created and overrides aren't needed.
                self.cancel_timer_handle(SCHEDULE_OVERRIDE)
                self.timers[SCHEDULE_OVERRIDE] = self.run_in(self.clear_overrides, self.duration)

    def clear_overrides(self, kwargs):
        self.log('Clearing overrides: {}'.format(self.overrides), level = self._level)
        del self.overrides[:]

    def override(self, entity, attribute, old, new, kwargs):
        """ Override the current light timer and do not restore the state """
        self.log('{}: {}'.format(entity, new), level = self._level)
        if entity not in self.timers:
            # The timer has not started because the door is still open.
            # Therefor we need to add it to the overrides so that the timer does not get created.
            self.overrides.append(entity)

        self.cancel_timer_handle(entity)

    def restore_state(self, kwargs):
        entity = kwargs.get(SCHEDULE_ENTITY)
        self.cancel_listen_state_handle(entity)

        state = self.get_snapshot(entity)
        if state:
            self.log('Recalling state: {}'.format(state.tostring()), level = self._level)

            if state.state == STATE_ON:
                # This must be a entity with different attributes.
                self.turn_on(entity, **state.attributes)
            elif state.state == STATE_OFF:
                # pretty much everything without differing attributes will be turned off.
                self.turn_off(entity)

    def turn_on_if_off(self, entity_id, attributes={}):
        """ Track and turn on entity if the entity is off """
        self.log("Turn on if off: {}".format((entity_id, attributes)), level = self._level)
        if self.get_state(entity_id) == STATE_OFF:
            if not self.have_snapshot(entity_id):
                self.take_snapshot(entity_id)

            if attributes:
                self.turn_on(entity_id, **attributes)
            else:
                self.turn_on(entity_id)
        # attributes are considered off if the state is not equal to the configured state.   
        elif any([ self.get_state(entity_id, attribute=attr) != value for attr, value in attributes.items() ]):
            if not self.have_snapshot(entity_id):
                self.take_snapshot(entity_id)

            self.turn_on(entity_id, **attributes)

    def start_timer_handle(self, entity_id):
        kwargs = {SCHEDULE_ENTITY:entity_id}
        self.cancel_timer_handle(entity_id)
        self.log("Starting timer handle '{}'".format(entity_id), level = self._level)
        self.timers[entity_id] = self.run_in(self.restore_state, self.duration, **kwargs)

    def cancel_timer_handle(self, entity_id):
        """ Cancel a timer for the provided entity_id """
        if entity_id in self.timers:
            self.log("Canceling timer handle '{}'".format(entity_id), level = self._level)
            self.cancel_timer(self.timers[entity_id])

    def start_listen_state_handle(self, entity_id):
        """ Starts a handle to listen if the off button is pressed """
        self.cancel_listen_state_handle(entity_id)
        self.log("Starting listen state handle '{}'".format(entity_id), level = self._level)
        self.handles[entity_id] = self.listen_state(self.override, entity_id, new = STATE_OFF)

    def cancel_listen_state_handle(self, entity_id):
        """ Cancel a listen state handle for the provided entity_id """
        if entity_id in self.handles:
            self.log("Canceling listen state handle '{}'".format(entity_id), level = self._level)
            self.cancel_listen_state(self.handles[entity_id])

    def take_snapshot(self, entity_id):
        """ Store a momentary state in time """
        state = self.get_state(entity_id, attribute=ALL)
        self._set_stored_state(**state)
        return state.get(STATE)

    def have_snapshot(self, entity_id):
        return self._get_stored_state(entity_id) is not None

    def get_snapshot(self, entity_id):
        return self._pop_stored_state(entity_id)

    def _set_stored_state(self, entity_id, **kwargs):
        state = kwargs.get(STATE)
        attributes = kwargs.get(ATTRIBUTES, {})
        if state is not None:
            state = StoredState(entity_id, state, attributes)
            self.log('Storing State: {}'.format(state.tostring()), level=self._level)
            self._stored_states[entity_id] = state
        else:
            self.log("No state found for '{}'!".format(entity_id), level=LOG_ERROR)
        
    def _get_stored_state(self, entity_id):
        state = self._stored_states.get(entity_id)
        if state:
            self.log('Getting State: {}'.format(state.tostring()), level=self._level)
            return state
        return None
        
    def _pop_stored_state(self, entity_id):
        if entity_id in self._stored_states:
            state = self._stored_states.pop(entity_id)
            self.log('Popping State: {}'.format(state.tostring()), level=self._level)
            return state
        return None

    def terminate(self):
        for entity in self.handles.keys():
            self.cancel_listen_state_handle(entity)
            
        for entity in self.timers.keys():
            self.cancel_timer_handle(entity)

class AppEntity(object):
    def __init__(self, config_entity):
        self.attributes = {}
        if isinstance(config_entity, dict):
            self.entity_id = config_entity.get(CONF_ENTITY)
            self.attributes = config_entity.get(CONF_DATA, {})            
        elif isinstance(config_entity, str):
            self.entity_id = config_entity

class StoredState(object):
    def __init__(self, entity_id, state, attributes={}):
        self._entity_id = entity_id
        self._state = state
        self._attributes = { k: v for k, v in attributes.items() if k in LIGHT_ATTRIBUTES }

    @property
    def entity_id(self):
        return self._entity_id

    @property
    def state(self):
        return self._state

    @property
    def attributes(self):
        return self._attributes

    def __repr__(self):
        return self._entity_id
        
    def tostring(self):
        return f"{{'entity_id':{self._entity_id}, 'state':{self._state}, 'attributes':{self._attributes}}}"
