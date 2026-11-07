"use client";

import MuiDrawer from "@/cfflch/components/mui-drawer";
import { Box } from "@mui/material";
import "@/cfflch/css/layout.css";

export default function RoutesLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>): React.ReactElement {
  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: { xs: "column", sm: "row" },
        overflow: "hidden",
      }}
    >
      <MuiDrawer />
      <Box sx={{ display: "flex", justifyContent: "center", width: "100%" }}>
        {children}
      </Box>
    </Box>
  );
}