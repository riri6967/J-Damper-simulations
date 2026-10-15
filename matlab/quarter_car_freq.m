function H = quarter_car_freq(f, p, Q)
%QUARTER_CAR_FREQ Linear quarter-car frequency responses to road displacement.
%   H = QUARTER_CAR_FREQ(f, p, Q)
%   f : frequency vector [Hz] (column)
%   p : parameter struct (INERTER_PARAMS)
%   Q : suspension mechanical admittance Q(jw) = force/velocity [N s/m],
%       complex vector the same size as f. Build it from elements:
%         spring k/s,  damper c,  inerter b*s (fluid inerter: b*s + c_par)
%         parallel: Q1 + Q2,   series: 1/(1/Q1 + 1/Q2)
%   Returns complex transfer functions per unit road displacement:
%     H.Ft  dynamic tyre force [N/m]
%     H.acc sprung-mass acceleration [1/s^2]
%     H.st  suspension travel zs-zu [-]

s  = 1i*2*pi*f(:);
Y  = s .* Q(:);                                   % force / relative displacement
Zu = p.kt ./ (p.mu_u*s.^2 + p.kt + Y.*p.ms.*s.^2 ./ (p.ms*s.^2 + Y));
Zs = Y.*Zu ./ (p.ms*s.^2 + Y);

H.Ft  = p.kt .* (1 - Zu);
H.acc = s.^2 .* Zs;
H.st  = Zs - Zu;
end
