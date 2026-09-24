import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],

  build: {
    lib: {
      entry: "src/main.tsx",
      name: "AirflowPlugin",
      formats: ["umd"],
      fileName: () => "main.umd.cjs",
    },

    rollupOptions: {
      external: [
        "react",
        "react-dom",
        "react/jsx-runtime",
      ],

      output: {
        globals: {
          react: "React",
          "react-dom": "ReactDOM",
          "react/jsx-runtime": "ReactJSXRuntime",
        },
      },
    },
  },
});