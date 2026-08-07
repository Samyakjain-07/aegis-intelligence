import { createBrowserRouter } from "react-router";
import { Layout } from "./components/Layout";
import { Chat } from "./pages/Chat";
import { Library } from "./pages/Library";
import { Compare } from "./pages/Compare";
import { Admin } from "./pages/Admin";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: Layout,
    children: [
      { index: true, Component: Chat },
      { path: "library", Component: Library },
      { path: "compare", Component: Compare },
      { path: "admin", Component: Admin },
    ],
  },
]);
