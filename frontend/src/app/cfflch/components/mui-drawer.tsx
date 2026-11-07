"use client";

import { Drawer, Box, MenuItem, IconButton } from "@mui/material";
import MenuIcon from "@mui/icons-material/Menu";
import { useState } from "react";
import { useRouter } from "next/navigation";

export default function MuiDrawer(): React.ReactElement {
  const [open, setOpen] = useState(false);
  const router = useRouter();

  function navigate(path: string): void {
    setOpen(false);
    router.push(path);
  }

  return (
    <>
      <Box
        p={2}
        height="100%"
        textAlign="left"
        sx={{
          backgroundColor: "#292929",
          padding: { xs: "0px", sm: "10px" },
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
            sx={{ fontSize: 35 }}
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

          <MenuItem
            sx={{ color: "white" }}
            onClick={() => navigate("/cfflch/search")}
          >
            Search
          </MenuItem>
          <MenuItem
            sx={{ color: "white" }}
            onClick={() => navigate("/cfflch/results")}
          >
            Results
          </MenuItem>
        </Box>
      </Drawer>
    </>
  );
}