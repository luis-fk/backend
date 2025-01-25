"use client";
import { Drawer, Box, Typography } from "@mui/material";
import DrawerIcon from "./DrawerIcon";
import MenuIcon from "@mui/icons-material/Menu";
import { useState } from "react";

export default function MuiDrawer() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <Box
        p={2}
        width="200px"
        height="100%"
        textAlign="left"
        sx={{ backgroundColor: "#292929" }}
      >
        <DrawerIcon
          open={open}
          element={<MenuIcon sx={{ fontSize: 40 }} />}
          onClick={() => setOpen(true)}
        />
      </Box>

      <Drawer anchor="left" open={open} onClose={() => setOpen(false)}>
        <Box
          p={2}
          width="200px"
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
