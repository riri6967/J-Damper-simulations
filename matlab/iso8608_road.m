function [out1, out2] = iso8608_road(p, arg, mode)
%ISO8608_ROAD ISO 8608 road displacement PSD or time-domain realisation.
%   Gd = ISO8608_ROAD(p, f, 'psd')  returns the temporal displacement PSD [m^2/Hz]
%        at frequencies f [Hz] for speed p.V. One-sided: Gd(f) = Gd(n)/V, n = f/V.
%   [t, zr] = ISO8608_ROAD(p, T, 'time') returns a realisation of duration T [s]
%        built by harmonic superposition with random phases (fixed seed, so runs
%        are repeatable).

switch mode
    case 'psd'
        n = arg / p.V;
        out1 = p.Gd_n0 * (n / p.n0).^(-2) / p.V;
    case 'time'
        T  = arg;
        fs = 1000;
        t  = (0:1/fs:T)';
        f  = (0.2:0.05:50)';                 % [Hz] band of interest
        df = 0.05;
        Gd = iso8608_road(p, f, 'psd');
        A  = sqrt(2*Gd*df);
        rng(1);
        ph = 2*pi*rand(size(f));
        zr = zeros(size(t));
        for k = 1:numel(f)
            zr = zr + A(k)*sin(2*pi*f(k)*t + ph(k));
        end
        out1 = t; out2 = zr;
    otherwise
        error('mode must be ''psd'' or ''time''');
end
end
