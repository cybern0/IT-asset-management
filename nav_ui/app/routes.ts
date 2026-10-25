import { type RouteConfig, index, layout, route } from "@react-router/dev/routes";

export default [
  route("image/:id", "routes/image.tsx"),
  layout("routes/shell.tsx", [
    index("routes/home.tsx"),
    route("dashboard", "routes/dashboard.tsx"),
    route("assets/:group/:tab?", "routes/module.tsx", { id: "assets" }),
    route("administration/:group/:tab?", "routes/module.tsx", { id: "administration" }),
    route("*", "routes/notfound.tsx"),
  ]),
] satisfies RouteConfig;
