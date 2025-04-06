"use client";
import { IconButton } from "@mui/material";
import { ReactNode } from "react";

interface DrawerIconProps {
  open?: boolean;
  element?: ReactNode;
  onClick?: () => void;
}

export default function DrawerIcon({
  open,
  element,
  onClick,
}: DrawerIconProps) {
  return (
    <IconButton size="large" edge="start" color="inherit" onClick={onClick}>
      {open ? null : element}
    </IconButton>
  );
}
