import logging
import math
from typing import Callable, Optional

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from graphql import GraphQLInputObjectType, GraphQLNonNull, GraphQLObjectType, get_named_type

_LOGGER = logging.getLogger(__name__)

GET_DEVICES_QUERY = gql(
    """
    query getDevices($accountNumber: String!) {
      devices(accountNumber: $accountNumber) {
        id
        label: name
        provider
        deviceType
        status {
          current
          currentState
          isSuspended
        }
        ... on SmartFlexVehicle {
          make
          model
        }
        ... on SmartFlexChargePoint {
          make
          model
        }
      }
    }
    """
)

GET_DEVICE_PREFERENCES_QUERY = gql(
    """
    query getDevicePreferences($accountNumber: String!, $deviceId: String!) {
      devices(accountNumber: $accountNumber, deviceId: $deviceId) {
        id
        status {
          isSuspended
        }
        ... on SmartFlexVehicle {
          chargingPreferences {
            weekdayTargetTime
            weekdayTargetSoc
            weekendTargetTime
            weekendTargetSoc
            minimumSoc
            maximumSoc
          }
        }
        ... on SmartFlexChargePoint {
          chargingPreferences {
            weekdayTargetTime
            weekdayTargetSoc
            weekendTargetTime
            weekendTargetSoc
            minimumSoc
            maximumSoc
          }
        }
      }
    }
    """
)

GET_DEVICE_DISPATCHES_QUERY = gql(
    """
    query getDeviceDispatches($accountNumber: String!, $deviceId: String!) {
      devices(accountNumber: $accountNumber, deviceId: $deviceId) {
        id
        status {
          currentState
        }
      }
      flexPlannedDispatches(deviceId: $deviceId) {
        start
        end
        type
        energyAddedKwh
      }
      completedDispatches(accountNumber: $accountNumber) {
        start
        end
        delta
        meta {
          source
          location
        }
      }
    }
    """
)


class OctopusEnergyGraphQLClient:

  def __init__(self, api_key: str):
    if api_key is None:
      raise Exception('API KEY is not set')

    self._api_key = api_key
    self._base_url = "https://api.octopus.energy/v1/graphql/"
    self._session: Optional[Client] = None

  async def async_get_accounts(self) -> list[str]:
    return await self.__async_execute_with_session(self.__async_get_accounts)

  async def async_get_devices(self, account_id: str):
    return await self.__async_execute_with_session(
      lambda session: self.__async_get_devices(session, account_id)
    )

  async def async_get_device_preferences(self, account_id: str, device_id: str):
    return await self.__async_execute_with_session(
      lambda session: self.__async_get_device_preferences(session, account_id, device_id)
    )

  async def async_get_device_dispatches(self, account_id: str, device_id: str):
    return await self.__async_execute_with_session(
      lambda session: self.__async_get_device_dispatches(session, account_id, device_id)
    )

  async def async_get_charge_preferences(self, account_id: str):
    return await self.__async_execute_with_session(
      lambda session: self.__async_get_charge_preferences(session, account_id)
    )

  async def async_set_charge_preferences(
    self,
    account_id: str,
    readyByHoursAfterMidnight: float,
    targetSocPercent: int,
    device_id: Optional[str] = None,
  ):
    return await self.__async_execute_with_session(
      lambda session: self.__async_set_charge_preferences(
        session,
        account_id,
        readyByHoursAfterMidnight,
        targetSocPercent,
        device_id,
      )
    )

  async def async_trigger_boost_charge(self, account_id: str, device_id: Optional[str] = None):
    return await self.__async_execute_with_session(
      lambda session: self.__async_trigger_boost_charge(session, account_id, device_id)
    )

  async def async_cancel_boost_charge(self, account_id: str, device_id: Optional[str] = None):
    return await self.__async_execute_with_session(
      lambda session: self.__async_cancel_boost_charge(session, account_id, device_id)
    )

  async def async_suspend_smart_charging(self, account_id: str, device_id: Optional[str] = None):
    return await self.__async_execute_with_session(
      lambda session: self.__async_suspend_smart_charging(session, account_id, device_id)
    )

  async def async_resume_smart_charging(self, account_id: str, device_id: Optional[str] = None):
    return await self.__async_execute_with_session(
      lambda session: self.__async_resume_smart_charging(session, account_id, device_id)
    )

  async def __async_get_token(self) -> str:
    transport = AIOHTTPTransport(url=self._base_url)
    async with Client(transport=transport, fetch_schema_from_transport=True) as session:
      query = gql(
        '''
          mutation krakenTokenAuthentication($apiKey: String!) {
            obtainKrakenToken(input: { APIKey: $apiKey }) {
              token
            }
          }
        '''
      )
      params = {"apiKey": self._api_key}
      result = await session.execute(query, variable_values=params, operation_name="krakenTokenAuthentication")
      return result['obtainKrakenToken']['token']

  async def __async_get_session(self, reset: bool = False):
    if reset:
      self._session = None

    if self._session is not None:
      return self._session

    token = await self.__async_get_token()
    headers = {"Authorization": token}
    transport = AIOHTTPTransport(url=self._base_url, headers=headers)
    self._session = Client(transport=transport, fetch_schema_from_transport=True)
    return self._session

  async def __async_execute_with_session(self, func: Callable[[Client], object]):
    try:
      async with await self.__async_get_session() as session:
        return await func(session)
    except Exception:
      async with await self.__async_get_session(reset=True) as session:
        return await func(session)

  async def __async_set_charge_preferences(
    self,
    session,
    account_id: str,
    readyByHoursAfterMidnight: float,
    targetSocPercent: int,
    device_id: Optional[str],
  ):
    targetSocPercent = 5 * math.ceil(round(targetSocPercent) / 5)
    readyByHoursAfterMidnight = 0.5 * round(readyByHoursAfterMidnight / 0.5)

    if readyByHoursAfterMidnight < 4 or readyByHoursAfterMidnight > 11:
        raise ValueError("Target time must be between 4AM and 11AM")
    if targetSocPercent < 10 or targetSocPercent > 100:
        raise ValueError("Target SOC percent must be between 10 and 100")

    ready_hours = int(readyByHoursAfterMidnight)
    ready_mins = round(60 * (readyByHoursAfterMidnight % 1))
    target_time = f"{ready_hours:02}:{ready_mins:02}"

    device_id = device_id or await self.__async_get_device_id(session, account_id)
    if device_id is None:
      raise Exception('Failed to find intelligent device id for account')

    days_of_week = [
      "MONDAY",
      "TUESDAY",
      "WEDNESDAY",
      "THURSDAY",
      "FRIDAY",
      "SATURDAY",
      "SUNDAY",
    ]
    schedules = ", ".join(
      f"{{\n  dayOfWeek: {day}\n  time: \"{target_time}\"\n  max: {targetSocPercent}\n}}"
      for day in days_of_week
    )

    query = gql(
      f'''
        mutation setDevicePreferences($deviceId: ID!) {{
          setDevicePreferences(input: {{
            deviceId: $deviceId
            mode: CHARGE
            unit: PERCENTAGE
            schedules: [{schedules}]
          }}) {{
            id
          }}
        }}
      '''
    )

    params = {"deviceId": device_id}
    result = await session.execute(query, variable_values=params, operation_name="setDevicePreferences")
    return result['setDevicePreferences']

  async def __async_trigger_boost_charge(self, session, account_id: str, device_id: Optional[str]):
    mutation_name, field_info = self.__select_boost_charge_mutation(
      session,
      action="trigger",
      device_id=device_id,
    )
    query, params = self.__build_boost_charge_mutation(
      mutation_name,
      field_info,
      account_id,
      device_id,
      action="BOOST",
    )
    result = await session.execute(query, variable_values=params, operation_name=mutation_name)
    return result[mutation_name]

  async def __async_cancel_boost_charge(self, session, account_id: str, device_id: Optional[str]):
    mutation_name, field_info = self.__select_boost_charge_mutation(
      session,
      action="cancel",
      device_id=device_id,
    )
    query, params = self.__build_boost_charge_mutation(
      mutation_name,
      field_info,
      account_id,
      device_id,
      action="CANCEL",
    )
    result = await session.execute(query, variable_values=params, operation_name=mutation_name)
    return result[mutation_name]

  def __select_boost_charge_mutation(self, session, *, action: str, device_id: Optional[str]):
    schema = getattr(getattr(session, "client", None), "schema", None)
    mutation_type = getattr(schema, "mutation_type", None) if schema else None
    fields = getattr(mutation_type, "fields", {}) if mutation_type else {}
    if not fields:
      return ("triggerBoostCharge" if action == "trigger" else "deleteBoostCharge"), {
        "arg_mode": "input",
        "input_fields": {},
        "arg_fields": {},
      }

    action = action.lower()
    expected_name = "triggerboostcharge" if action == "trigger" else "deleteboostcharge"
    candidates: list[tuple[str, object, dict]] = []

    for name, field in fields.items():
      lname = name.lower()
      if "boost" not in lname or "charge" not in lname:
        continue
      if action == "trigger" and not any(key in lname for key in ("trigger", "start", "update")):
        continue
      if action == "cancel" and not any(key in lname for key in ("delete", "cancel", "stop", "update")):
        continue
      info = self.__describe_mutation_field(field)
      if device_id and not info.get("supports_device"):
        continue
      candidates.append((name, field, info))

    if not candidates and fields:
      name = "triggerBoostCharge" if action == "trigger" else "deleteBoostCharge"
      field = fields.get(name)
      if field:
        info = self.__describe_mutation_field(field)
        candidates.append((name, field, info))

    if not candidates:
      return ("triggerBoostCharge" if action == "trigger" else "deleteBoostCharge"), {
        "arg_mode": "input",
        "input_fields": {},
        "arg_fields": {},
      }

    def _score(item):
      name, _, info = item
      score = 0
      if name.lower() == expected_name:
        score += 2
      if "updateboostcharge" in name.lower():
        score += 1
      if info.get("supports_device"):
        score += 1
      if info.get("supports_account"):
        score += 1
      if info.get("supports_action"):
        score += 1
      return score

    mutation_name, _, info = sorted(candidates, key=_score, reverse=True)[0]
    if device_id and not info.get("supports_device"):
      _LOGGER.warning(
        "Boost charge mutation '%s' does not support device targeting; default device will be used.",
        mutation_name,
      )
    return mutation_name, info

  def __describe_mutation_field(self, field) -> dict:
    arg_fields = getattr(field, "args", {}) or {}
    input_fields = {}
    supports_device = False
    supports_account = False
    supports_action = False
    action_field = None
    arg_mode = "direct"
    return_type = get_named_type(getattr(field, "type", None)) if getattr(field, "type", None) else None
    if "input" in arg_fields:
      input_type = get_named_type(arg_fields["input"].type)
      if isinstance(input_type, GraphQLInputObjectType):
        input_fields = input_type.fields
        supports_device = any(key in input_fields for key in ("deviceId", "krakenflexDeviceId"))
        supports_account = any(key in input_fields for key in ("accountNumber", "accountId"))
        for key in ("action", "boostAction", "boostChargeAction"):
          if key in input_fields:
            supports_action = True
            action_field = key
            break
        arg_mode = "input"
    else:
      supports_device = any(key in arg_fields for key in ("deviceId", "krakenflexDeviceId"))
      supports_account = any(key in arg_fields for key in ("accountNumber", "accountId"))
      for key in ("action", "boostAction", "boostChargeAction"):
        if key in arg_fields:
          supports_action = True
          action_field = key
          break
    return {
      "arg_mode": arg_mode,
      "input_fields": input_fields,
      "arg_fields": arg_fields,
      "supports_device": supports_device,
      "supports_account": supports_account,
      "supports_action": supports_action,
      "action_field": action_field,
      "return_type": return_type,
    }

  def __build_boost_charge_mutation(
    self,
    mutation_name: str,
    field_info: dict,
    account_id: str,
    device_id: Optional[str],
    action: str,
  ):
    arg_mode = field_info.get("arg_mode", "input")
    input_fields = field_info.get("input_fields", {})
    arg_fields = field_info.get("arg_fields", {})
    action_field = field_info.get("action_field")

    account_field = None
    for key in ("accountNumber", "accountId"):
      if key in input_fields or key in arg_fields:
        account_field = key
        break

    device_field = None
    for key in ("deviceId", "krakenflexDeviceId"):
      if key in input_fields or key in arg_fields:
        device_field = key
        break

    def _type_info(field_type):
      required = isinstance(field_type, GraphQLNonNull)
      named = get_named_type(field_type)
      type_name = named.name if named else "String"
      return type_name, required

    var_defs: list[str] = []
    params = {}
    input_entries: list[str] = []

    if arg_mode == "input":
      if account_field and account_field in input_fields:
        account_type, account_required = _type_info(input_fields[account_field].type)
        var_defs.append(f"${account_field}: {account_type}{'!' if account_required else ''}")
        params[account_field] = account_id
        input_entries.append(f"{account_field}: ${account_field}")

      if device_id and device_field and device_field in input_fields:
        device_type, device_required = _type_info(input_fields[device_field].type)
        var_defs.append(f"${device_field}: {device_type}{'!' if device_required else ''}")
        params[device_field] = device_id
        input_entries.append(f"{device_field}: ${device_field}")
      if action_field and action_field in input_fields:
        action_type, action_required = _type_info(input_fields[action_field].type)
        var_defs.append(f"${action_field}: {action_type}{'!' if action_required else ''}")
        params[action_field] = action
        input_entries.append(f"{action_field}: ${action_field}")

      var_block = f"({', '.join(var_defs)})" if var_defs else ""
      input_block = ", ".join(input_entries)
      selection = self.__mutation_selection_for(field_info)
      query = gql(
        f"""
        mutation {mutation_name}{var_block} {{
          {mutation_name}(input: {{ {input_block} }}) {selection}
        }}
        """
      )
      return query, params

    call_args = []
    if account_field and account_field in arg_fields:
      account_type, account_required = _type_info(arg_fields[account_field].type)
      var_defs.append(f"${account_field}: {account_type}{'!' if account_required else ''}")
      params[account_field] = account_id
      call_args.append(f"{account_field}: ${account_field}")
    if device_id and device_field and device_field in arg_fields:
      device_type, device_required = _type_info(arg_fields[device_field].type)
      var_defs.append(f"${device_field}: {device_type}{'!' if device_required else ''}")
      params[device_field] = device_id
      call_args.append(f"{device_field}: ${device_field}")
    if action_field and action_field in arg_fields:
      action_type, action_required = _type_info(arg_fields[action_field].type)
      var_defs.append(f"${action_field}: {action_type}{'!' if action_required else ''}")
      params[action_field] = action
      call_args.append(f"{action_field}: ${action_field}")

    var_block = f"({', '.join(var_defs)})" if var_defs else ""
    call_block = ", ".join(call_args)
    selection = self.__mutation_selection_for(field_info)
    query = gql(
      f"""
      mutation {mutation_name}{var_block} {{
        {mutation_name}({call_block}) {selection}
      }}
      """
    )
    return query, params

  def __mutation_selection_for(self, field_info: dict) -> str:
    return_type = field_info.get("return_type")
    if isinstance(return_type, GraphQLObjectType):
      return "{ __typename }"
    return "{ __typename }"

  async def __async_get_accounts(self, session):
    query = gql(
      '''
        query viewer {
          viewer {
            accounts {
              number
            }
          }
        }
      '''
    )

    result = await session.execute(query, variable_values={}, operation_name="viewer")
    return [acc['number'] for acc in result['viewer']['accounts']]

  async def __async_get_charge_preferences(self, session, account_id: str):
    query = gql(
      '''
        query vehicleChargingPreferences($accountNumber: String!) {
          vehicleChargingPreferences(accountNumber: $accountNumber) {
            weekdayTargetTime
            weekdayTargetSoc
            weekendTargetTime
            weekendTargetSoc
          }
        }
      '''
    )

    params = {"accountNumber": account_id}
    result = await session.execute(query, variable_values=params, operation_name="vehicleChargingPreferences")
    return result['vehicleChargingPreferences']

  async def __async_get_devices(self, session, account_id: str):
    params = {"accountNumber": account_id}
    result = await session.execute(
      GET_DEVICES_QUERY,
      variable_values=params,
      operation_name="getDevices",
    )
    return result.get('devices', []) if isinstance(result, dict) else []

  async def __async_get_device_preferences(self, session, account_id: str, device_id: str):
    params = {"accountNumber": account_id, "deviceId": device_id}
    result = await session.execute(
      GET_DEVICE_PREFERENCES_QUERY,
      variable_values=params,
      operation_name="getDevicePreferences",
    )
    devices = result.get('devices', []) if isinstance(result, dict) else []
    return devices[0] if devices else None

  async def __async_get_device_dispatches(self, session, account_id: str, device_id: str):
    params = {"accountNumber": account_id, "deviceId": device_id}
    return await session.execute(
      GET_DEVICE_DISPATCHES_QUERY,
      variable_values=params,
      operation_name="getDeviceDispatches",
    )

  async def __async_get_device_info(self, session, account_id: str):
    query = gql(
      '''
        query registeredKrakenflexDevice($accountNumber: String!) {
          registeredKrakenflexDevice(accountNumber: $accountNumber) {
            krakenflexDeviceId
            provider
            vehicleMake
            vehicleModel
            vehicleBatterySizeInKwh
            chargePointMake
            chargePointModel
            chargePointPowerInKw
            status
            suspended
            hasToken
            createdAt
          }
        }
      '''
    )

    params = {"accountNumber": account_id}
    result = await session.execute(query, variable_values=params, operation_name="registeredKrakenflexDevice")
    return result['registeredKrakenflexDevice']

  async def __async_get_device_id(self, session, account_id: str):
    try:
      devices = await self.__async_get_devices(session, account_id)
      for device in devices:
        if device and device.get('status', {}).get('current') == 'LIVE':
          return device.get('id')
    except Exception as ex:  # pylint: disable=broad-exception-caught
      _LOGGER.debug("Could not determine live device id: %s", ex)

    info = await self.__async_get_device_info(session, account_id)
    return info['krakenflexDeviceId'] if info and 'krakenflexDeviceId' in info else None

  async def __async_suspend_smart_charging(self, session, account_id: str, device_id: Optional[str]):
    device_id = device_id or await self.__async_get_device_id(session, account_id)
    if device_id is None:
      raise Exception('Failed to find intelligent device id for account')

    query = gql(
      '''
        mutation updateDeviceSmartControl($deviceId: ID!) {
          updateDeviceSmartControl(input: { deviceId: $deviceId, action: SUSPEND }) {
            id
          }
        }
      '''
    )

    params = {"deviceId": device_id}
    result = await session.execute(query, variable_values=params, operation_name="updateDeviceSmartControl")
    return result['updateDeviceSmartControl']

  async def __async_resume_smart_charging(self, session, account_id: str, device_id: Optional[str]):
    device_id = device_id or await self.__async_get_device_id(session, account_id)
    if device_id is None:
      raise Exception('Failed to find intelligent device id for account')

    query = gql(
      '''
        mutation updateDeviceSmartControl($deviceId: ID!) {
          updateDeviceSmartControl(input: { deviceId: $deviceId, action: UNSUSPEND }) {
            id
          }
        }
      '''
    )

    params = {"deviceId": device_id}
    result = await session.execute(query, variable_values=params, operation_name="updateDeviceSmartControl")
    return result['updateDeviceSmartControl']
