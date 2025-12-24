import logging
import math
from typing import Callable, Optional

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport

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
    query = gql(
      '''
        mutation triggerBoostCharge($accountNumber: String!, $deviceId: ID) {
          triggerBoostCharge(input: { accountNumber: $accountNumber, deviceId: $deviceId }) {
            krakenflexDevice {
              krakenflexDeviceId
            }
          }
        }
      '''
    )

    params = {"accountNumber": account_id, "deviceId": device_id}
    result = await session.execute(query, variable_values=params, operation_name="triggerBoostCharge")
    return result['triggerBoostCharge']

  async def __async_cancel_boost_charge(self, session, account_id: str, device_id: Optional[str]):
    query = gql(
      '''
        mutation deleteBoostCharge($accountNumber: String!, $deviceId: ID) {
          deleteBoostCharge(input: { accountNumber: $accountNumber, deviceId: $deviceId }) {
            krakenflexDevice {
              krakenflexDeviceId
            }
          }
        }
      '''
    )

    params = {"accountNumber": account_id, "deviceId": device_id}
    result = await session.execute(query, variable_values=params, operation_name="deleteBoostCharge")
    return result['deleteBoostCharge']

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


