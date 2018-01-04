"""LBControl2 API.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import datetime
import logging

import enum
import suds

from . import soap_endpoint

_LOGGER = logging.getLogger(__name__)


def _merge_dict(merge_from, merge_into):
    """Recursively merges merge_from -> merge_into.

    Eg.:
    >>> d = {'nested': {'a': 'b'}}
    >>> d.update({'nested': {'new': 'entry'}})
    {'nested': {'new': 'entry'}}

    vs.

    >>> _merge_dict({'nested': {'new': 'entry'}}, d)
    {'nested': {'a': 'b', 'new': 'entry'}}
    """
    if not isinstance(merge_from, dict):
        raise TypeError('Please provide a dictionary')

    for key in merge_from:
        if key in merge_into:
            if isinstance(merge_into[key], dict)\
                    and isinstance(merge_from[key], dict):
                _merge_dict(merge_from[key], merge_into[key])
            else:
                merge_into[key] = merge_from[key]
        else:
            merge_into[key] = merge_from[key]

    return merge_into


class SOAPError(Exception):
    """Error communicating with the LBControl backend"""
    pass


class LBCObject(object):
    """Base class for all object returned by LBControl2 interface."""
    __slots__ = ()

    def __init__(self, **kwargs):
        for key in self.__slots__:
            setattr(self, key, kwargs[key])

    def __repr__(self):
        return '%s(%s%s)' % (self.__class__.__name__,
                             self.name,
                             ('[%s]' % self.id
                              if getattr(self, 'id', None)
                              else ''))

    def __str__(self):
        return '{}({})'.format(self.__class__.__name__,
                               ', '.join(['{}={}'.format(key, getattr(
                                   self, key)) for key in self.__slots__]))

    @classmethod
    def from_soap(cls, soap_data):
        """Create a LBCObject object from SOAP data"""
        try:
            parsed_data = cls._parse_soap(soap_data)

        except AttributeError as err:
            raise SOAPError('Unable to parse SOAP data: %s' % err)

        # We need to pass the parsed_data dictionnary to the constructor
        return cls(**parsed_data)


class LBCVirtual(LBCObject):
    """A LB Virtual object, as returned by get_virtual."""
    __slots__ = ('active',
                 'cluster',
                 'conn_timeout',
                 'eonid',
                 'hold',
                 'id',
                 'ip',
                 'name',
                 'owner',
                 'persist_timeout',
                 'persist_type',
                 'pool',
                 'rules',
                 'template',
                 'prodstatus',)

    @classmethod
    def _parse_soap(cls, soap_virtual):
        """Create a LBCVirtual object from SOAP data"""
        # We need access to private member of these autogen SOAP classes
        # pylint: disable=W0212
        active = getattr(soap_virtual, '_active', False)
        result = dict(
            name=soap_virtual._name,
            id=soap_virtual._id,
            ip=soap_virtual._ipAddress,
            cluster='TODO',  # soap_virtual.cluster,
            hold=soap_virtual._hold,
            active=active,
            pool=None,
            rules=[
                LBCRule.from_soap(rule)
                for rule in getattr(soap_virtual, 'rules', [])
            ],
            eonid=soap_virtual._eonid,
            template=(LBCTemplate.from_soap(soap_virtual.template)
                      if 'template' in soap_virtual
                      else None),
            owner=soap_virtual._owner,
            conn_timeout=getattr(soap_virtual, '_conntimeout', None),
            persist_timeout=getattr(soap_virtual, '_persisttimeout', None),
            persist_type=getattr(soap_virtual, '_persisttype', None),
            prodstatus=None,
        )

        prodstatus = getattr(soap_virtual, '_prodstatus', None)
        if prodstatus is not None:
            try:
                result['prodstatus'] = ProdStatus(prodstatus).name
            except ValueError:
                pass

        # Port 0 virtuals may not have pool assicoated with them.
        if hasattr(soap_virtual, 'pool'):
            result['pool'] = LBCPool.from_soap(soap_virtual.pool)
        return result


class LBCVirtualSummary(LBCObject):
    """A LB Virtual Summary object, as returned by list_virtuals."""
    __slots__ = ('name', 'id', 'cluster')

    @classmethod
    def _parse_soap(cls, soap_virtual):
        """Create a LBCVirtualSummary object from SOAP data"""
        # We need access to private member of these autogen SOAP classes
        # pylint: disable=W0212
        return dict(
            name=soap_virtual._name,
            id=soap_virtual._id,
            cluster=soap_virtual._cluster,
        )


class LBCVirtualSummaryList(LBCObject):
    """A list of LB Virtual Summary object, as returned by list_virtuals."""

    @classmethod
    def parse_soap(cls, soap_virtuals):
        """Create a LBCVirtualSummary object from SOAP data"""
        # We need access to private member of these autogen SOAP classes
        # pylint: disable=W0212
        return [LBCVirtualSummary.from_soap(virtual)
                for virtual in soap_virtuals]


class LBCRule(LBCObject):
    """A LB Rule object as returned by get_rule."""
    __slots__ = ('name', 'id',
                 'rule',
                 'pool')

    @classmethod
    def _parse_soap(cls, soap_rule):
        """Create a LBCRule object from SOAP data."""
        # We need access to private member of these autogen SOAP classes
        # pylint: disable=W0212
        return dict(
            name=soap_rule._name,
            id=soap_rule._id,
            rule=soap_rule._ruleString,
            pool=(LBCPool.from_soap(soap_rule.pool)
                  if hasattr(soap_rule, 'pool')
                  else None),
        )


class LBCTemplate(LBCObject):
    """A LB Template object."""
    __slots__ = ('name', 'id', 'location', 'version',)

    @classmethod
    def _parse_soap(cls, soap_template):
        """Create a LBCTemplate object from SOAP data"""
        # We need access to private member of these autogen SOAP classes
        # pylint: disable=W0212
        return dict(name=soap_template._name,
                    id=soap_template._id,
                    location=getattr(soap_template, '_location', None),
                    version=getattr(soap_template, '_version', None),)


class SvcDownAction(enum.Enum):
    """LBControl2 service down action."""
    # W0232: Enums do not have an init method
    # pylint: disable=W0232
    none = 'NONE_SRVCDOWNACTION_ENUM'
    reset = 'RESET_SRVCDOWNACTION_ENUM'
    drop = 'DROP_SRVCDOWNACTION_ENUM'
    reselect = 'RESELECT_SRVCDOWNACTION_ENUM'


class LbMethod(enum.Enum):
    """LBControl2 load balancing methods."""
    # W0232: Enums do not have an init method
    # pylint: disable=W0232
    round_robin = 'ROUND_ROBIN_LBENUM'
    member_ratio = 'MEMBER_RATIO_LBENUM'
    member_least_conn = 'MEMBER_LEAST_CONN_LBENUM'
    member_observed = 'MEMBER_OBSERVED_LBENUM'
    member_predictive = 'MEMBER_PREDICTIVE_LBENUM'
    ratio = 'NODE_RATIO_LBENUM'
    least_conn = 'LEAST_CONN_LBENUM'
    fastest = 'FASTEST_LBENUM'
    observed = 'OBSERVED_LBENUM'
    predictive = 'PREDICTIVE_LBENUM'
    dynamic_ratio = 'DYNAMIC_RATIO_LBENUM'
    fastest_app_resp = 'FASTEST_APP_RESP_LBENUM'
    least_sessions = 'LEAST_SESSIONS_LBENUM'
    member_dynamic_ratio = 'MEMBER_DYNAMIC_RATIO_LBENUM'
    l3_addr = 'L3_ADDR_LBENUM'


class LBCPool(LBCObject):
    """A LB Pool object, as returned by get_pool."""
    __slots__ = ('name', 'id',
                 'min_active',
                 'svc_down_action',
                 'lb_method', 'members')

    @classmethod
    def _parse_soap(cls, soap_pool):
        """Create a LBCPool object from SOAP data"""
        # We need access to private member of these autogen SOAP classes
        # pylint: disable=W0212
        lb_method = getattr(soap_pool, 'lbmethod', None)
        if not lb_method:
            lb_method = getattr(soap_pool, '_lbmethod', None)

        # XXX: GetPool() returns the lb method in a "non defined
        # format". Spaces are replaced with _ so no apostrophe is
        # needed in the CLI
        if lb_method:
            lb_method = lb_method.replace(' ', '_')
        return dict(name=soap_pool._name,
                    id=soap_pool._id,
                    min_active=getattr(soap_pool, '_minactive', None),
                    svc_down_action=getattr(soap_pool, '_svcdownact', None),
                    lb_method=lb_method,
                    members=[LBCPoolMember.from_soap(m)
                             for m in getattr(soap_pool, 'members', [])],)


class LBCPoolMember(LBCObject):
    """A LB Pool Member object, as returned by get_pool."""
    __slots__ = ('active',
                 'forcedown',
                 'service')

    @classmethod
    def _parse_soap(cls, soap_pool_member):
        """Create a LBCPoolMember object from SOAP data"""
        # We need access to private member of these autogen SOAP classes
        # pylint: disable=W0212
        return dict(
            active=soap_pool_member._active,
            forcedown=soap_pool_member._forcedown,
            service=LBCService.from_soap(soap_pool_member.service)
        )

    # No name/id, so define a custom repr
    def __repr__(self):
        return 'LBCPoolMember(%r)' % self.service


class LBCService(LBCObject):
    """A LB Pool Member Service object, as returned by get_pool."""
    __slots__ = ('protocol', 'name',
                 'ip', 'port')

    @classmethod
    def _parse_soap(cls, soap_service):
        """Create a LBCService object from SOAP data"""
        # We need access to private member of these autogen SOAP classes
        # pylint: disable=W0212
        return dict(
            protocol=soap_service._protocol,
            name=soap_service._name,
            ip=soap_service._ipAddress,
            port=soap_service._port,
        )


class DeviceConfigState(enum.Enum):
    """LBControl2 device config state."""
    # W0232: Enums do not have an init method
    # pylint: disable=W0232
    none = 0
    enabled = 1
    suspended = 2
    force_down = 3
    not_found = 4
    unknown = 5


class LBCServiceHealth(LBCObject):
    """LBControl2 pool service health."""
    __slots__ = ('ip_addr',
                 'port',
                 'device_config_state')

    @classmethod
    def _parse_soap(cls, soap_service_health):
        """Create a LBCServiceHealth object from SOAP data"""
        # We need access to private member of these autogen SOAP classes
        # pylint: disable=W0212
        device_config = DeviceConfigState(int(soap_service_health._devConfig))
        return dict(
            ip_addr=soap_service_health._ipAddr,
            port=soap_service_health._port,
            device_config_state=device_config,
        )

    def __repr__(self):
        return 'LBCServiceHealth(%s:%d dev:%s)' % (
            self.ip_addr,
            self.port,
            self.device_config_state.name,
        )


class ProdStatus(enum.Enum):
    """LBControl2 prod status."""
    # W0232: Enums do not have an init method
    # pylint: disable=W0232
    prod = 0
    uat = 1
    qa = 2  # pylint: disable=C0103
    dev = 3


class LBCPoolHealth(LBCObject):
    """A LB Pool Health object, as returned by `virtual_pool_status`.
    """
    __slots__ = ('name',
                 'service_healths')

    @classmethod
    def _parse_soap(cls, soap_pool_health):
        """Create a LBCPoolHealth object from SOAP data"""
        # We need access to private member of these autogen SOAP classes
        # pylint: disable=W0212
        return dict(
            name=soap_pool_health._name,
            service_healths=[
                LBCServiceHealth.from_soap(soap_service_health)
                for soap_service_health in getattr(soap_pool_health,
                                                   'serviceHealthList', [])
            ]
        )

    # No id, so define a custom repr
    def __repr__(self):
        return 'LBCPoolHealth(%r)' % self.name


class LBControl2(object):
    """LBControl2 API."""

    def __init__(self, environment, enduser=None):
        # Create the client
        self._cnx = soap_endpoint.connect(environment, enduser)

    def list_virtuals(self, search, raw=False):
        """Retrieve LB Virtuals."""
        _LOGGER.debug('ListVirtuals(%r)', search)
        try:
            res = self._cnx.service.ListVirtuals(0, search)
        except suds.WebFault as err:
            raise SOAPError(err)

        if res:
            if raw:
                return res
            else:
                return LBCVirtualSummaryList.parse_soap(res)
        return []

    def list_pools(self, fuzzy_search):
        """Retrieve LB Pools."""
        _LOGGER.debug('ListPools(%r)', fuzzy_search)
        try:
            return self._cnx.service.ListPools(fuzzy_search)
        except suds.WebFault as err:
            raise SOAPError(err)

    def create_virtual(self, name, virtual):
        """Create LB Virtual."""
        virtual['_name'] = name
        virtual['_mtime'] = datetime.datetime.now().isoformat()
        _LOGGER.debug('CreateVirtual(%s)', name)
        try:
            return self._cnx.service.CreateVirtual(virtual)
        except suds.WebFault as err:
            raise SOAPError(err)

    def get_monitor(self, name):
        """Get LB monitor"""
        _LOGGER.debug('GetMonitor(%s)', name)
        try:
            return self._cnx.service.GetMonitor(name)
        except suds.WebFault as err:
            raise SOAPError(str(err))

    def get_service(self, name):
        """Get LB service"""
        _LOGGER.debug('GetService(%s)', name)
        try:
            return self._cnx.service.GetService(name)
        except suds.WebFault as err:
            raise SOAPError(str(err))

    def create_pool(self, name, pool):
        """Create LB Virtual pool."""
        pool['_name'] = name
        pool['_mtime'] = datetime.datetime.now().isoformat()
        _LOGGER.debug('CreatePool(%r)', pool)
        try:
            return self._cnx.service.CreatePool(pool)
        except suds.WebFault as err:
            raise SOAPError(str(err))

    def update_pool(self, pool):
        """Update LB Virtual pool."""
        _LOGGER.debug('UpdatePool(%r)', pool)
        try:
            return self._cnx.service.UpdatePool(pool)
        except suds.WebFault as err:
            raise SOAPError(err)

    def get_virtual(self, virtual_name, raw=False):
        """Retrieve LB Virtual information."""
        _LOGGER.debug('GetVirtual(%r)', virtual_name)
        try:
            res = self._cnx.service.GetVirtual(virtual_name)
        except suds.WebFault as err:
            raise SOAPError(err)

        if res:
            if raw:
                return res
            else:
                return LBCVirtual.from_soap(res)
        return None

    def update_virtual(self, virtual_name, new_settings, raw=False):
        """Update LB Virtual settings."""
        new_settings['_name'] = virtual_name
        _LOGGER.debug('UpdateVirtual(%r)', virtual_name)
        try:
            old_settings = self._cnx.service.GetVirtual(virtual_name)
            self._cnx.service.UpdateVirtual(_merge_dict(new_settings,
                                                        old_settings))

            res = self._cnx.service.GetVirtual(virtual_name)
        except suds.WebFault as err:
            raise SOAPError(err)

        if res:
            if raw:
                return res
            else:
                return LBCVirtual.from_soap(res)
        return None

    def delete_virtual(self, virtual_name):
        """Delete a LB Virtual."""
        _LOGGER.debug('DeleteVirtual(%r)', virtual_name)
        try:
            res = self._cnx.service.DeleteVirtual(virtual_name)

        except suds.WebFault as err:
            raise SOAPError(err)

        return res

    def push_virtual(self, virtual_name):
        """Push current LB Virtual configuration to the devices."""
        _LOGGER.debug('PushVirtual(%r)', virtual_name)
        try:
            res = self._cnx.service.PushVirtual(virtual_name)

        except suds.WebFault as err:
            raise SOAPError(err)

        return res

    def get_pool(self, pool_name, raw=False):
        """Retrieve a LB Pool."""
        _LOGGER.debug('GetPool(%r)', pool_name)
        try:
            res = self._cnx.service.GetPool(pool_name)
        except suds.WebFault as err:
            raise SOAPError(err)

        if res:
            if raw:
                return res
            else:
                return LBCPool.from_soap(res)
        return None

    def virtual_pool_status(self, virtual_name, pool_name):
        """Query the load balancer for the status of a virtual's pool."""
        _LOGGER.debug('VirtualPoolStatus(%s, %s)', virtual_name, pool_name)
        try:
            res = self._cnx.service.VirtualPoolStatus(virtual_name, pool_name)
        except suds.WebFault as err:
            _LOGGER.exception(err)
            raise SOAPError(err)

        if res:
            return LBCPoolHealth.from_soap(res)

        return None

    def is_pool_owner(self, pool_name):
        """Returns True if the current enduser is an owner of the LB Pool."""
        _LOGGER.debug('isPoolOwner(%r)', pool_name)
        try:
            res = self._cnx.service.isPoolOwner(pool_name)

        except suds.WebFault as err:
            raise SOAPError(err)

        return res

    def delete_pool(self, pool_name):
        """Delete a LB Pool.

        Note: Will fail if still used by an LB Virtual.
        """
        _LOGGER.debug('DeletePool(%r)', pool_name)
        try:
            res = self._cnx.service.DeletePool(pool_name)

        except suds.WebFault as err:
            raise SOAPError(err)

        return res

    def edit_pool_parameters(self,
                             pool_name,
                             virtual_name,
                             lb_method=None,
                             min_active=None,
                             svc_down_action=None,
                             svc_to_add=(),
                             svc_to_rm=()):
        """Edit a LB Pool parameters (including pool membership)."""
        # We need access to private member of these autogen SOAP classes
        # Enums are scriptable-objects despite E1136
        # pylint: disable=W0212,E1136
        pdata = self._cnx.factory.create('pePoolData')
        pdata._poolName = str(pool_name)
        pdata._virtualName = str(virtual_name)
        if lb_method:
            pdata._lbMethod = LbMethod[lb_method].value
        if min_active:
            pdata._minActive = int(min_active)
        if svc_down_action:
            pdata._serviceDownAction = SvcDownAction[svc_down_action].value

        services = []
        if svc_to_add:
            services.extend([
                self._service_data_p2s(
                    svc.get('service_name', None),
                    svc.get('hostname', None),
                    svc.get('port', None),
                    svc.get('priority', None),
                    svc.get('ratio', None),
                    svc.get('limit', None),
                    action='add',
                )
                for svc in svc_to_add
            ])
        if svc_to_rm:
            services.extend([
                self._service_data_p2s(
                    svc.get('service_name', None),
                    svc.get('hostname', None),
                    svc.get('port', None),
                    svc.get('priority', None),
                    svc.get('ratio', None),
                    svc.get('limit', None),
                    action='remove',
                )
                for svc in svc_to_rm
            ])
        pdata.services = services

        _LOGGER.debug('EditPoolParameters(%r)', pdata)
        try:
            res = self._cnx.service.EditPoolParameters(pdata)

        except suds.WebFault as err:
            raise SOAPError(err)

        return res

    def update_pool_parameters(self,
                               pool_name,
                               virtual_name,
                               lb_method=None,
                               min_active=None,
                               svc_down_action=None,
                               svc_to_add=(),
                               svc_to_rm=()):
        """
        Update a LB Pool parameters and making sure that no setting is
        lost during the update.
        """
        try:
            params = self.get_pool(pool_name)
            _LOGGER.debug('GetPool(%s)', params)
        except suds.WebFault as err:
            raise SOAPError(err)

        new_params = {}
        new_params['lb_method'] =\
            lb_method or params.lb_method or 'round_robin'
        new_params['min_active'] = min_active or params.min_active
        new_params['svc_down_action'] =\
            svc_down_action or params.svc_down_action

        return self.edit_pool_parameters(pool_name,
                                         virtual_name,
                                         svc_to_add=svc_to_add,
                                         svc_to_rm=svc_to_rm,
                                         **new_params)

    def modify_pool_member_state(self, virtual_name, pool_name, services,
                                 transition_type):
        """Modify the state of the members of a LB Pool."""
        # We need access to private member of these autogen SOAP classes
        # pylint: disable=W0212
        assert transition_type.upper() in {'ACTIVATE', 'SUSPEND', 'FORCEDOWN'}
        cdatas = []
        for svc in services:
            cdata = self._cnx.factory.create('poolMemberTransition')
            cdata._poolName = str(pool_name)
            cdata._virtualName = str(virtual_name)
            cdata._transitionType = str(transition_type)
            cdata._serviceName = svc.get('service_name', '')
            cdata._serviceIP = svc.get('ip', '')
            cdata._servicePort = svc.get('port', '')
            cdatas.append(cdata)

        if cdatas:
            _LOGGER.debug('ModifyPoolMemberState(%r)', cdatas)
            try:
                res = self._cnx.service.ModifyPoolMemberState(cdatas)

            except suds.WebFault as err:
                raise SOAPError(err)

            return res

        else:
            return None

    def _service_data_p2s(self, service_name, hostname, port,
                          priority, ratio, limit,
                          action):
        """Create a LB Service object (for a SOAP call)."""
        # We need access to private member of these autogen SOAP classes
        # pylint: disable=W0212
        assert action in [None, 'add', 'remove']
        sdata = self._cnx.factory.create('peServiceData')
        if service_name:
            sdata._serviceName = str(service_name)
        if hostname:
            sdata._hostName = str(hostname)
        if port is not None:
            sdata._port = int(port)
        if priority:
            sdata._priority = int(priority)
        if ratio:
            sdata._ratio = int(ratio)
        if limit:
            sdata._limit = int(limit)

        if action == 'add':
            sdata._isNew = True
            sdata._mustRemove = False
        elif action == 'remove':
            sdata._isNew = False
            sdata._mustRemove = True

        return sdata
