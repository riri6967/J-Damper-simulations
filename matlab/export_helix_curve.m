function export_helix_curve(n_turns, leg_len, fname)
%EXPORT_HELIX_CURVE Write the helix centreline for DesignModeler (Concept > 3D Curve).
%   EXPORT_HELIX_CURVE() writes a 3-turn helix with straight tangent legs to
%   ../cfd/helix_centerline.txt using the baseline geometry.
%   EXPORT_HELIX_CURVE(n_turns, leg_len, fname) overrides the defaults.
%   Format per line: group_id point_id x y z   (units: mm)

p = inerter_params();
if nargin < 1, n_turns = 3; end
if nargin < 2, leg_len = 5*p.d; end
if nargin < 3
    fname = fullfile(fileparts(mfilename('fullpath')), '..', 'cfd', 'helix_centerline.txt');
end

pts_per_turn = 72;
th = linspace(0, 2*pi*n_turns, n_turns*pts_per_turn + 1)';
c  = p.p_h/(2*pi);                         % axial rise per radian
helix = [p.R_h*cos(th), p.R_h*sin(th), c*th];

% Unit tangents at both ends, used to build the straight legs
t0 = [0, p.R_h, c];            t0 = t0/norm(t0);
te = [-p.R_h*sin(th(end)), p.R_h*cos(th(end)), c];  te = te/norm(te);
s  = linspace(0, leg_len, 6)';
leg_in  = flipud(helix(1,:) - s(2:end)*t0);
leg_out = helix(end,:) + s(2:end)*te;

xyz = [leg_in; helix; leg_out] * 1e3;      % m -> mm

fid = fopen(fname, 'w');
assert(fid > 0, 'Cannot open %s', fname);
for k = 1:size(xyz, 1)
    fprintf(fid, '1 %d %.6f %.6f %.6f\n', k, xyz(k,1), xyz(k,2), xyz(k,3));
end
fclose(fid);
fprintf('Wrote %d points (%d turns, legs %.1f mm) to %s\n', ...
    size(xyz,1), n_turns, leg_len*1e3, fname);
end
