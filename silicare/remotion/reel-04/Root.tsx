import React from "react";
import { Composition } from "remotion";
import { DURATION, FPS, H, W } from "./geometry";
import { Reel04 } from "./Reel04";

export const Root: React.FC = () => (
  <Composition id="SilicareReel04" component={Reel04} durationInFrames={DURATION} fps={FPS} width={W} height={H} />
);
