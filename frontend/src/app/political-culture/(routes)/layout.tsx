"use client";
import MuiDrawer from "@/app/political-culture/components/MuiDrawer";
import { Box, useMediaQuery } from "@mui/material";
import "@/political-culture/css/layout.css";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const isMobile = useMediaQuery("(max-width: 800px)");
  const flexDirection = isMobile ? "column" : "row";

  return (
    <>
      <Box
        sx={{
          display: "flex",
          flexDirection: flexDirection,
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
