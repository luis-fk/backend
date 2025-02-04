"use client";
import { Drawer, Box, Typography, useMediaQuery } from "@mui/material";
import DrawerIcon from "./DrawerIcon";
import MenuIcon from "@mui/icons-material/Menu";
import { useState } from "react";

export default function MuiDrawer() {
  const [open, setOpen] = useState(false);

  const isMobile = useMediaQuery("(max-width: 900px)");
  const boxIconPaddingTop = isMobile ? "0px" : "10px";
  const iconFontSize = isMobile ? 20 : 40;

  return (
    <>
      <Box
        p={2}
        height="100%"
        textAlign="left"
        sx={{
          backgroundColor: "#292929",
          padding: boxIconPaddingTop,
          paddingLeft: "10px",
        }}
      >
        <DrawerIcon
          open={open}
          element={<MenuIcon sx={{ fontSize: iconFontSize }} />}
          onClick={() => setOpen(true)}
        />
      </Box>

      <Drawer anchor="left" open={open} onClose={() => setOpen(false)}>
        <Box
          p={2}
          width="150px"
          height="100%"
          textAlign="left"
          sx={{ backgroundColor: "#0f0f0f" }}
        >
          <DrawerIcon
            open={!open}
            element={<MenuIcon sx={{ fontSize: 40, color: "white" }} />}
            onClick={() => setOpen(false)}
          />

          <Typography
            variant="h6"
            component="div"
            sx={{ paddingTop: "10px", color: "white" }}
          >
            Chat
          </Typography>

          <Typography
            variant="h6"
            component="div"
            sx={{ paddingTop: "10px", color: "white" }}
          >
            Statistics
          </Typography>
        </Box>
      </Drawer>
    </>
  );
}
