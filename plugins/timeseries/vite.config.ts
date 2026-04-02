import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  mode: "development",
  plugins: [react({ jsxRuntime: "classic" })],
  build: {
    minify: false,
    lib: {
      entry: path.resolve(__dirname, "./src/index.tsx"),
      name: "TimeSeriesPanel",
      fileName: (format) => `index.${format}.js`,
      formats: ["umd"],
    },
    rollupOptions: {
      external: [
        "react",
        "react-dom",
        "recoil",
        "@fiftyone/state",
        "@fiftyone/plugins",
        "@fiftyone/operators",
        "@fiftyone/spaces",
        "@fiftyone/components",
        "@fiftyone/components/src/components/ThemeProvider",
        "@fiftyone/playback",
        "@fiftyone/utilities",
      ],
      output: {
        globals: {
          react: "React",
          "react-dom": "ReactDOM",
          recoil: "recoil",
          "@fiftyone/state": "__fos__",
          "@fiftyone/plugins": "__fop__",
          "@fiftyone/operators": "__foo__",
          "@fiftyone/spaces": "__fosp__",
          "@fiftyone/components": "__foc__",
          "@fiftyone/components/src/components/ThemeProvider": "__foc__",
          "@fiftyone/playback": "__fopb__",
          "@fiftyone/utilities": "__fou__",
        },
      },
    },
  },
  define: {
    "process.env.NODE_ENV": '"development"',
  },
  optimizeDeps: {
    exclude: ["react", "react-dom"],
  },
});
