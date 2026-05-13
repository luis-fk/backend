"use client";
import { Drawer, Box, MenuItem, IconButton } from "@mui/material";
import MenuIcon from "@mui/icons-material/Menu";
import { useState } from "react";

export default function MuiDrawer() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <Box
        p={2}
        height="100%"
        textAlign="left"
        sx={{
          backgroundColor: "#292929",
          padding: { xs: "0px", "@media (min-width: 800px)": "10px" },
          paddingLeft: "10px",
        }}
      >
        <IconButton
          size="large"
          edge="start"
          color="inherit"
          onClick={() => setOpen(true)}
        >
          <MenuIcon
            sx={{ fontSize: { xs: 35, "@media (min-width: 800px)": 35 } }}
          />
        </IconButton>
      </Box>

      <Drawer anchor="left" open={open} onClose={() => setOpen(false)}>
        <Box
          p={2}
          width="150px"
          height="100%"
          textAlign="left"
          sx={{ backgroundColor: "#0f0f0f" }}
        >
          <IconButton
            color="inherit"
            onClick={() => setOpen(false)}
            sx={{ color: "white" }}
          >
            <MenuIcon sx={{ fontSize: 35 }} />
          </IconButton>

          <MenuItem sx={{ color: "white" }}>Chat</MenuItem>
          <MenuItem
            sx={{
              color: "rgba(255,255,255,0.4)",
              cursor: "default",
              pointerEvents: "none",
            }}
          >
            Statistics
          </MenuItem>
        </Box>
      </Drawer>
    </>
  );
}
