"use client";
import MuiDrawer from "@/app/plants/components/MuiDrawer";
import { Box } from "@mui/material";
import "@/plants/css/layout.css";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <>
      <Box
        sx={{
          display: "flex",
          flexDirection: { xs: "column", "@media (min-width: 800px)": "row" },
          overflow: "hidden",
        }}
      >
        <MuiDrawer></MuiDrawer>
        <Box sx={{ display: "flex", justifyContent: "center", width: "100%" }}>
          {children}
        </Box>
      </Box>
    </>
  );
}