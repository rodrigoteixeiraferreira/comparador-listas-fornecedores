import type { NextConfig } from "next";

// a demo não é um site público: fica fora dos buscadores e não abre dentro de outro site
const config: NextConfig = {
  poweredByHeader: false,
  agentRules: false, // o next dev não escreve AGENTS.md no repositório
  devIndicators: false, // o selo do modo de desenvolvimento não aparece nos prints
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Robots-Tag", value: "noindex, nofollow" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "same-origin" },
          { key: "X-Content-Type-Options", value: "nosniff" },
        ],
      },
    ];
  },
};

export default config;
