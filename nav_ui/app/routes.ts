import { type RouteConfig, index, layout, route } from "@react-router/dev/routes";

export default [
  layout("routes/shell.tsx", [
    index("routes/home.tsx"),
    route("assets/:group/:tab?", "routes/module.tsx", { id: "assets" }),
    route("administration/:group/:tab?", "routes/module.tsx", { id: "administration" }),
    route("*", "routes/notfound.tsx"),
  ]),
] satisfies RouteConfig;
