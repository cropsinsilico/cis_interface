import os
import pandas as pd
from yggdrasil import units, tools, multitasking
from yggdrasil.drivers.DSLModelDriver import DSLModelDriver


_default_agg = 'mean'
_default_interp = 'index'


class TimeSyncModelDriver(DSLModelDriver):
    r"""Class for synchronizing states for timesteps between two models.

    Args:
        synonyms (dict, optional): Mapping from model names to mappings
            from base variables names to information about one or
            more alternate variable names used by the named model
            that should be converted to the base variable. Values for
            providing information about alternate variables can either
            be strings (implies equivalence with the base variable in
            everything but name and units) or mappings with the keys:

              alt (str, list): Name of one or more variables used by
                 the model that should be used to calculate the named
                 base variable.
              alt2base (function): Callable object that takes the
                 alternate variables named by the 'alt' property as
                 input and returns the base variable.
              base2alt (function): Callable object that takes the base
                 variable as input and returns the alternate variables
                 named by the 'alt' property.

            Defaults to an empty dictionary.
        aggregation (str, dict, optional): Method(s) that should be used
            to aggregate synonymous variables across models. This can
            be a single method that should be used for all synonymous
            variables or a dictionary mapping between synonymous variables
            and the method that should be used by that variable. If a
            variable is not present in the dictionary or a values is
            not provided, 'mean' will be used. See the documentation
            for pandas.DataFrame.aggregate for available options.
        interpolation (str, dict, optional): Method(s) or keyword
            arguments that should be used to interpolate missing
            timesteps. This can be a single method or a dictionary
            mapping between model name and the interpolation methods
            (or keyword arguments) that should be used for variables
            from that model. Defaults to 'index'. See the documentation
            for pandas.DataFrame.interpolate for available options.
        additional_variables (dict, optional): Mapping from model
            name to a list of variables from other models that are
            not provided by the model, but should still be returned
            to the model. Defaults to empty dictionary.

    """

    _schema_subtype_description = ('Model is dedicated to synchronizing'
                                   'timesteps between other models.')
    _schema_properties = {
        'synonyms': {'type': 'object',
                     'additionalProperties': {
                         'type': 'object',
                         'additionalProperties': {'anyOf': [
                             {'type': 'string'},
                             {'type': 'object',
                              'required': ['alt', 'alt2base', 'base2alt'],
                              'properties': {
                                  'alt': {'anyOf': [
                                      {'type': 'string'},
                                      {'type': 'array',
                                       'items': {'type': 'string'}}]},
                                  'alt2base': {'type': 'function'},
                                  'base2alt': {'type': 'function'}}}]}},
                     'default': {}},
        'interpolation': {
            'anyOf': [{'type': 'string'},
                      {'type': 'object',
                       'additionalProperties': {'oneOf': [
                           {'type': 'string'},
                           {'type': 'object',
                            'required': ['method'],
                            'properties': {
                                'method': {'type': 'string'}}}]}},
                      {'type': 'object',
                       'required': ['method'],
                       'properties': {
                           'method': {'type': 'string'}}}],
            'default': _default_interp},
        'aggregation': {
            'anyOf': [{'type': 'function'},
                      {'type': 'string'},
                      {'type': 'object',
                       'additionalProperties': {
                           'anyOf': [{'type': 'function'},
                                     {'type': 'string'}]}}],
            'default': _default_agg},
        'additional_variables': {
            'type': 'object',
            'additionalProperties': {'type': 'array',
                                     'items': {'type': 'string'}},
            'default': {}}}
    language = 'timesync'
    executable_type = 'other'

    def __init__(self, name, *args, **kwargs):
        super(TimeSyncModelDriver, self).__init__(name, *args, **kwargs)
        # Ensure that options are uniform in their format and check
        # that they are valid
        for k, v in self.synonyms.items():
            for s0, x in list(v.items()):
                if isinstance(x, str):
                    x = {'alt': x, 'alt2base': None, 'base2alt': None}
                if not isinstance(x['alt'], list):
                    x['alt'] = [x['alt']]
                if ((((x['alt2base'] is None) or (x['base2alt'] is None))
                     and (len(x['alt']) > 1))):  # pragma: debug
                    raise RuntimeError(
                        ('Cannot convert from multiple alternate '
                         'variables (%s) to single base variable (%s) '
                         'without transformation functions.')
                        % (x['alt'], s0))
                v[s0] = x
        if isinstance(self.interpolation, str):
            self.interpolation = {'method': self.interpolation}
        if 'method' not in self.interpolation:
            for k, v in list(self.interpolation.items()):
                if isinstance(v, str):
                    v = {'method': v}
                    self.interpolation[k] = v

    def parse_arguments(self, args, **kwargs):
        r"""Sort model arguments to determine which one is the executable
        and which ones are arguments.

        Args:
            args (list): List of arguments provided.
            **kwargs: Additional keyword arguments are ignored.

        """
        assert(isinstance(args, list) and (len(args) == 0))
        self.model_file = 'dummy'
        
    @property
    def model_wrapper_args(self):
        r"""tuple: Positional arguments for the model wrapper."""
        return (self.name, self.synonyms, self.interpolation,
                self.aggregation, self.additional_variables)

    @classmethod
    def model_wrapper(cls, name, synonyms, interpolation,
                      aggregation, additional_variables, env=None):
        r"""Model wrapper."""
        from yggdrasil.languages.Python.YggInterface import YggTimesyncServer
        if env is not None:
            os.environ.update(env)
        rpc = YggTimesyncServer(name)
        threads = {}
        times = []
        tables = {}
        table_units = {'base': {}}
        table_lock = multitasking.RLock()
        default_agg = _default_agg
        if not isinstance(aggregation, dict):
            default_agg = aggregation
            aggregation = {}
        while True:
            # Check for errors on response threads
            for v in threads.values():
                if v.check_flag_attr('error_flag'):  # pragma: debug
                    for v in threads.values():
                        if v.is_alive():
                            v.terminate()
                    raise Exception("Error on response thread.")
            # Receive values from client models
            flag, values, request_id = rpc.recv_from(timeout=1.0)
            if not flag:
                print("timesync server: End of input.")
                break
            if len(values) == 0:
                rpc.sleep()
                continue
            t, state = values[:]
            t_pd = units.convert_to_pandas_timedelta(t)
            client_model = rpc.ocomm[
                rpc.requests[request_id].response_address].client_model
            # Remove variables marked as external so they are not merged
            external_variables = additional_variables.get(client_model, [])
            for k in external_variables:
                state.pop(k, None)
            internal_variables = list(state.keys())
            # Update record
            with table_lock:
                if client_model not in tables:
                    tables[client_model] = pd.DataFrame({'time': times})
                # Update units & aggregation methods
                if client_model not in table_units:
                    # NOTE: this assumes that units will not change
                    # between timesteps for a single model. Is there a
                    # case where this might not be true?
                    table_units[client_model] = {
                        k: units.get_units(v) for k, v in state.items()}
                    table_units[client_model]['time'] = units.get_units(t)
                    alt_vars = []
                    for k, v in synonyms.get(client_model, {}).items():
                        alt_vars += v['alt']
                        if v['alt2base'] is not None:
                            table_units[client_model][k] = units.get_units(
                                v['alt2base'](*[state[a] for a in v['alt']]))
                        else:
                            table_units[client_model][k] = table_units[
                                client_model][v['alt'][0]]
                    for k, v in table_units[client_model].items():
                        table_units['base'].setdefault(k, v)
                    for k in list(set(state.keys()) - set(alt_vars)):
                        aggregation.setdefault(k, default_agg)
                # Update the state
                if t_pd not in times:
                    times.append(t_pd)
                for model, table in tables.items():
                    new_data = {'time': [t_pd]}
                    if model == client_model:
                        new_data.update({k: [units.get_data(v)]
                                         for k, v in state.items()})
                    new_data = pd.DataFrame(new_data)
                    idx = table['time'].isin([t_pd])
                    if not idx.any():
                        table = table.append(new_data, sort=False)
                    elif model == client_model:
                        table = table.drop(table.index[idx])
                        table = table.append(new_data, sort=False)
                    tables[model] = table.sort_values('time')
            # Assign thread to handle checking when data is filled in
            threads[request_id] = multitasking.YggTaskLoop(
                target=cls.response_loop,
                args=(client_model, request_id, rpc, t_pd,
                      internal_variables, external_variables,
                      tables, table_units, table_lock,
                      synonyms, interpolation, aggregation))
            threads[request_id].start()
        # Cleanup threads (only called if there is an error since the
        # loop will only be broken when all of the clients have signed
        # off, implying that all requests have been responded to).
        for v in threads.values():
            if v.is_alive():  # pragma: debug
                v.wait(0.5)
        for v in threads.values():
            if v.is_alive():  # pragma: debug
                v.terminate()

    @classmethod
    def check_for_data(cls, time, tables, table_units, table_lock,
                       open_clients):
        r"""Check for a time in the tables to determine if there is
        sufficient data available to calculate the state.

        Args:
            time (pandas.Timedelta): Time that state is requested at.
            tables (dict): Mapping from model name to pandas DataFrames
                containing variables supplied by the model.
            table_units (dict): Mapping from model name to dictionaries
                mapping from variable names to units.
            table_lock (RLock): Thread-safe lock for accessing table.
            open_clients (list): Clients that are still open.

        Returns:
            bool: True if there is sufficient data, False otherwise.

        """
        with table_lock:
            for k, v in tables.items():
                if (k in open_clients) and (time > max(v.dropna()['time'])):
                    return False
            for k in open_clients:
                if k not in table_units:  # pragma: debug
                    return False
        return True

    @classmethod
    def response_loop(cls, client_model, request_id, rpc, time,
                      internal_variables, external_variables,
                      tables, table_units, table_lock,
                      synonyms, interpolation, aggregation):
        r"""Check for available data and send response if it is
        available.

        Args:
            client_model (str): Name of model that made the request.
            request_id (str): ID associated with request that should
                be responded to.
            rpc (ServerComm): Server RPC comm that should be used to
                reply to the request when the data is available.
            time (pandas.Timedelta): Time to get variables at.
            internal_variables (list): Variables that model is requesting
                that it also calculates.
            external_variables (list): Variables that model is requesting
                that will be provided by other models.
            tables (dict): Mapping from model name to pandas DataFrames
                containing variables supplied by the model.
            table_units (dict): Mapping from model name to dictionaries
                mapping from variable names to units.
            table_lock (RLock): Thread-safe lock for accessing table.
            synonyms (dict): Dictionary mapping from base variables to
                alternate variables and mapping functions used to convert
                between the variables. Defaults to empty dict and no
                conversions are performed.
            interpolation (dict): Mapping from model name to the
                interpolation kwargs that should be used. Defaults to
                empty dictionary.
            aggregation (dict): Mapping from variable name to the
                aggregation method that should be used. Defaults to
                empty dictionary.

        """
        if not (rpc.all_clients_connected
                and cls.check_for_data(time, tables, table_units, table_lock,
                                       rpc.open_clients)):
            # Don't start sampling until all clients have connected
            # and there is data available for the requested timestep
            tools.sleep(1.0)
            return
        tot = cls.merge(tables, table_units, table_lock, rpc.open_clients,
                        synonyms, interpolation, aggregation)
        # Update external units
        for k in external_variables:
            if k not in table_units[client_model]:
                table_units[client_model][k] = table_units['base'][k]
        # Check if data is available at the desired timestep?
        # Convert units
        for k in tot.columns:
            funits = units.get_conversion_function(table_units['base'][k],
                                                   table_units[client_model][k])
            tot[k] = tot[k].apply(funits)
        # Transform back to variables expected by the model
        for kbase, alt in synonyms.get(client_model, {}).items():
            if alt['base2alt'] is not None:
                alt_vars = alt['base2alt'](tot[kbase])
                if isinstance(alt_vars, (tuple, list)):
                    assert(len(alt_vars) == len(alt['alt']))
                    for k, v in zip(alt['alt'], alt_vars):
                        tot[k] = v
                else:
                    assert(len(alt['alt']) == 1)
                    tot[alt['alt'][0]] = alt_vars
            else:
                tot[alt['alt'][0]] = tot[kbase]
        # Get state
        state = {}
        for v in internal_variables + external_variables:
            v_res = tot.loc[time, v]
            state[v] = units.add_units(v_res, table_units[client_model][v])
        time_u = units.convert_to(units.convert_from_pandas_timedelta(time),
                                  table_units[client_model]['time'])
        flag = rpc.send_to(request_id, state)
        if not flag:  # pragma: debug
            raise RuntimeError(("Failed to send response to "
                                "request %s for time %s from "
                                "model %s.")
                               % (request_id, time_u, client_model))
        raise multitasking.BreakLoopException
    
    @classmethod
    def merge(cls, tables, table_units, table_lock, open_clients,
              synonyms, interpolation, aggregation):
        r"""Merge tables from models to get data.

        Args:
            tables (dict): Mapping from model name to pandas DataFrames
                containing variables supplied by the model.
            table_units (dict): Mapping from model name to dictionaries
                mapping from variable names to units.
            table_lock (RLock): Thread-safe lock for accessing table.
            open_clients (list): Clients that are still open.
            synonyms (dict): Dictionary mapping from base variables to
                alternate variables and mapping functions used to convert
                between the variables. Defaults to empty dict and no
                conversions are performed.
            interpolation (dict): Mapping from model name to the
                interpolation kwargs that should be used. Defaults to
                empty dictionary.
            aggregation (dict): Mapping from variable name to the
                aggregation method that should be used. Defaults to
                empty dictionary.


        """
        # Adjust input arguments
        interp_default = {'method': _default_interp}
        if 'method' in interpolation:
            interp_default = interpolation
            interpolation = {}
        # Interpolate
        table_temp = {}
        with table_lock:
            for k, v in tables.items():
                kws = interpolation.get(k, interp_default).copy()
                if k not in open_clients:
                    # Ensure that clients that have signed of are
                    # extrapolated, otherwise they would never produce
                    # valid data
                    kws['limit_area'] = None
                if 'order' in kws:
                    kws['order'] = min(v.dropna().shape[0] - 1,
                                       kws['order'])
                    if kws['order'] == 0:
                        kws.pop('order')
                        kws.update(interp_default)
                v = v.set_index('time')
                # Cannot interpolate on pandas timedelta as of pandas 1.0.1
                ind = v.index
                v.index = v.index.total_seconds()
                table_temp[k] = v.interpolate(**kws)
                table_temp[k].index = ind
        # Rename + transformation
        for model, v in table_temp.items():
            drop = []
            for kbase, alt in synonyms.get(model, {}).items():
                if alt['alt2base'] is not None:
                    args = [v[k] for k in alt['alt']]
                    v[kbase] = alt['alt2base'](*args)
                else:
                    v[kbase] = v[alt['alt'][0]]
                drop += alt['alt']
            for k in drop:
                v = v.drop(k, axis=1)
            # Units
            for k in v.columns:
                funits = units.get_conversion_function(table_units[model][k],
                                                       table_units['base'][k])
                v[k] = v[k].apply(funits)
            table_temp[model] = v
        # Append
        out = pd.DataFrame()
        for k, v in table_temp.items():
            out = out.append(v, sort=False)
        # Groupby + aggregate
        out = out.groupby('time').agg(aggregation)
        return out
