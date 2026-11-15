import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "VITE_");
  const useMock = env.VITE_USE_MOCK !== "false";

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: useMock
        ? undefined
        : {
            "/api": {
              target: "http://localhost:8000",
              changeOrigin: true
            },
            "/data": {
              target: "http://localhost:8000",
              changeOrigin: true
            }
          }
    }
  };
});
