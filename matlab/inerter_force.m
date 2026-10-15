function [F, F_b, F_loss, dp_loss] = inerter_force(xdd, xd, p)
%INERTER_FORCE Nonlinear quasi-steady force of a helical-channel fluid inerter.
%   [F, F_b, F_loss, dp_loss] = INERTER_FORCE(xdd, xd, p)
%   xdd, xd : relative acceleration [m/s^2] and velocity [m/s] across the inerter
%   p       : parameter struct from INERTER_PARAMS
%
%   F = b*xdd + A_p*dp_loss(v) + F_c*tanh(xd/v_s), with v = (A_p/A_c)*xd and
%   dp_loss = (f_D*l/d + K_in + K_out) * 0.5*rho*v*|v|.
%   The laminar friction term is evaluated in closed form so the result stays finite as v -> 0.

v  = (p.A_p / p.A_c) .* xd;
Re = p.rho .* abs(v) .* p.d ./ p.mu;
[f, regime] = friction_factor_helical(Re, p.delta);

% Laminar: f = (64/Re)*ratio  ->  f*l/d*0.5*rho*v|v| = 32*mu*l*v/d^2 * ratio
ratio = f .* max(Re, 1e-9) / 64;
dp_fric = 32 * p.mu * p.l .* v ./ p.d^2 .* ratio;
turb = regime == 1;
dp_fric(turb) = f(turb) .* p.l ./ p.d .* 0.5 .* p.rho .* v(turb) .* abs(v(turb));

dp_minor = (p.K_in + p.K_out) * 0.5 * p.rho .* v .* abs(v);
dp_loss  = dp_fric + dp_minor;

F_b    = p.b .* xdd;
F_loss = p.A_p .* dp_loss + p.F_c .* tanh(xd ./ p.v_s);
F      = F_b + F_loss;
end
