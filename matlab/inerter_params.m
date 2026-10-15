function p = inerter_params()
%INERTER_PARAMS Baseline parameters for the fluid inerter and the quarter-car.
%   p = INERTER_PARAMS() returns a struct. Change values here only; every
%   other script reads from this function.

%% Fluid: ISO VG 32 hydraulic oil at 40 degC (isothermal assumption)
p.rho   = 870;          % density [kg/m^3]
p.mu    = 0.028;        % dynamic viscosity [Pa s]
p.p_vap = 2e3;          % vapour pressure (approx.) [Pa]

%% Inerter geometry
p.D_p = 40e-3;          % piston bore [m]
p.d   = 6e-3;           % helical channel inner diameter [m]
p.R_h = 30e-3;          % helix radius to channel centreline [m]
p.p_h = 10e-3;          % helix pitch [m]
p.n   = 10;             % number of turns [-]

p.K_in  = 2.6;          % entry loss: drilled port + 2 sharp elbows (3D port CFD, Re 250-500)
p.K_out = 3.8;          % exit loss, same path (3D port CFD)
p.F_c   = 0;            % seal Coulomb friction [N] (0 = ignore)
p.v_s   = 1e-3;         % tanh smoothing velocity for friction [m/s]

%% Derived inerter quantities
p.A_p = pi*p.D_p^2/4;                               % piston area [m^2]
p.A_c = pi*p.d^2/4;                                 % channel area [m^2]
p.l   = p.n*sqrt((2*pi*p.R_h)^2 + p.p_h^2);         % channel length [m]
p.b   = p.rho*p.l*p.A_p^2/p.A_c;                    % ideal inertance [kg]
p.c_lin = 128*p.mu*p.l*p.A_p^2/(pi*p.d^4);          % straight-pipe laminar damping [N s/m]
p.delta = (p.d/2)/p.R_h;                            % curvature ratio r/R [-]

%% Quarter-car (GT / prototype race car corner - placeholder values)
p.ms = 250;             % sprung mass per corner [kg]
p.mu_u = 35;            % unsprung mass [kg]
p.ks = 80e3;            % wheel-rate spring stiffness [N/m]
p.cs = 4000;            % damper coefficient [N s/m]
p.kt = 300e3;           % tyre vertical stiffness [N/m]
p.g  = 9.81;

%% Road / speed
p.V      = 50;          % vehicle speed [m/s] (180 km/h)
p.Gd_n0  = 16e-6;       % ISO 8608 class A [m^3]
p.n0     = 0.1;         % reference spatial frequency [cycles/m]
end
