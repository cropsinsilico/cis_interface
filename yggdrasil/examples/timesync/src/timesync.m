
function timesync(t_step, t_units)

  t_step = str2num(t_step);
  fprintf('Hello from Matlab timesync: timestep = %f %s\n', t_step, t_units);
  t_step = t_step * str2symunit(t_units);
  t_start = 0.0000000000000001 * str2symunit(t_units);
  t_end = 5.0 * str2symunit('day');
  state = containers.Map('UniformValues', false, 'ValueType', 'any');
  state('x') = sin(2.0 * pi * t_start / (10.0 * str2symunit('day')));
  state('y') = cos(2.0 * pi * t_start / (5.0 * str2symunit('day')));

  % Set up connections matching yaml
  % Timestep connection will be 'timestep'
  timestep = YggInterface('YggTimestep', 'timestep');
  out = YggInterface('YggOutput', 'output');

  % Initialize state and synchronize with other models
  t = t_start;
  [ret, result] = timestep.call(t, state);
  if (~ret);
    error('timesync(Matlab): Initial sync failed.');
  end;
  state = result{1};

  % Send initial state to output
  msg_keys = keys(state);
  msg_keys{length(msg_keys) + 1} = 'time';
  msg_vals = values(state);
  msg_vals{length(msg_vals) + 1} = t;
  msg = containers.Map(msg_keys, msg_vals, 'UniformValues', false);
  flag = out.send(msg);

  % Iterate until end
  while (simplify(t/t_end) < 1)

    % Perform calculations to update the state
    t = t + t_step;
    state = containers.Map('UniformValues', false, 'ValueType', 'any');
    state('x') = sin(2.0 * pi * t / (10.0 * str2symunit('day')));
    state('y') = cos(2.0 * pi * t / (5.0 * str2symunit('day')));

    % Synchronize the state
    [ret, result] = timestep.call(t, state);
    if (~ret);
      error(sprintf('timesync(Matlab): sync for t=%f failed.\n', t));
    end;
    state = result{1};

    % Send output
    msg_keys = keys(state);
    msg_keys{length(msg_keys) + 1} = 'time';
    msg_vals = values(state);
    msg_vals{length(msg_vals) + 1} = t;
    msg = containers.Map(msg_keys, msg_vals, 'UniformValues', false);
    flag = out.send(msg);
    if (~flag);
      error(sprintf('timesync(Matlab): Failed to send output for t=%s.\n', t));
    end;
  end;

  disp('Goodbye from Matlab timestep');
  
end




