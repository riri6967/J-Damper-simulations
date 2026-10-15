function cpb = parasitic_ratio(p, d, xd_rep)
%PARASITIC_RATIO Parasitic damping per kg of inertance, c_par/b [1/s].
%   cpb = PARASITIC_RATIO(p, d, xd_rep) for channel diameter d [m], evaluated
%   at a representative inerter velocity xd_rep [m/s] (default 0.04, the RMS
%   inerter velocity found by run_time_domain.m for the L4 layout).
%   In laminar flow c_par/b = 32*nu/d^2 * (f_c/f_s), which does not depend on the
%   channel length or the piston area. The channel diameter alone sets how
%   lossy each kg of inertance is. Curvature enters through f_c/f_s.

if nargin < 3, xd_rep = 0.04; end
A_c   = pi*d^2/4;
delta = (d/2)/p.R_h;
Re    = p.rho * (p.A_p/A_c) * xd_rep * d / p.mu;
[f, regime] = friction_factor_helical(Re, delta);
if regime == 0
    cpb = 32*(p.mu/p.rho)/d^2 * (f*Re/64);
else
    % turbulent: linearise dp = f*l/d*0.5*rho*v^2 about v_rep
    v   = (p.A_p/A_c)*xd_rep;
    cpb = f*0.5*v / d;      % = (A_p*dp/xd_rep)/b
end
end
