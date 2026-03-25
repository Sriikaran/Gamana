import { useMemo, useState, useEffect } from 'react';
import * as THREE from 'three';
import SolutionVehicles3D from './SolutionVehicles3D';

const TrafficSignal = ({ position, rotation, state, boost }) => {
  return (
    <group position={position} rotation={rotation}>
      <mesh position={[0, 0.1, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[0.15, 0.15, 0.2, 16]} />
        <meshStandardMaterial color="#111111" roughness={0.9} />
      </mesh>
      <mesh position={[0, 1.5, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[0.06, 0.08, 3, 16]} />
        <meshStandardMaterial color="#2a2a2a" roughness={0.7} metalness={0.5} />
      </mesh>
      <mesh position={[0, 3.2, 0.5]} castShadow receiveShadow>
        <boxGeometry args={[0.4, 1.2, 0.4]} />
        <meshStandardMaterial color="#1a1a1a" roughness={0.8} />
      </mesh>
      <mesh position={[0, 3.5, 0.7]} castShadow>
        <boxGeometry args={[0.3, 0.05, 0.2]} />
        <meshStandardMaterial color="#000000" roughness={0.9} />
      </mesh>
      <mesh position={[0, 3.2, 0.7]} castShadow>
        <boxGeometry args={[0.3, 0.05, 0.2]} />
        <meshStandardMaterial color="#000000" roughness={0.9} />
      </mesh>
      <mesh position={[0, 2.9, 0.7]} castShadow>
        <boxGeometry args={[0.3, 0.05, 0.2]} />
        <meshStandardMaterial color="#000000" roughness={0.9} />
      </mesh>
      <mesh position={[0, 3.55, 0.71]}>
        <sphereGeometry args={[0.12, 16, 16]} />
        <meshStandardMaterial color="#ff3333" emissive="#ff0000" emissiveIntensity={state === 'red' ? 2.0 : 0} toneMapped={false} roughness={0.5} />
      </mesh>
      <mesh position={[0, 3.2, 0.71]}>
        <sphereGeometry args={[0.12, 16, 16]} />
        <meshStandardMaterial color="#ffcc00" emissive="#ffaa00" emissiveIntensity={state === 'yellow' ? 2.0 : 0} toneMapped={false} roughness={0.5} />
      </mesh>
      <mesh position={[0, 2.85, 0.71]}>
        <sphereGeometry args={[0.12, 16, 16]} />
        <meshStandardMaterial
          color={boost && state === 'green' ? "#88ff88" : "#33ff33"}
          emissive={boost && state === 'green' ? "#33ff33" : "#00ff00"}
          emissiveIntensity={state === 'green' ? (boost ? 4.5 : 2.0) : 0}
          toneMapped={false}
          roughness={0.5}
        />
      </mesh>
    </group>
  );
};

export default function SolutionIntersection3D() {
  const verticalRoadWidth = 10;
  const horizontalRoadWidth = 20; // 4 lanes: 5 units each
  const roadLength = 200;
  const roadThickness = 0.2;
  const roadYOffset = 0.1;
  const markingYOffset = roadYOffset + 0.105;

  // Traffic Controller
  const [nsLight, setNsLight] = useState('red');
  const [ewLight, setEwLight] = useState('green');
  const [ewBoost, setEwBoost] = useState(false);
  const [distActive, setDistActive] = useState(false);
  const [solving, setSolving] = useState(false);
  const [cycleCount, setCycleCount] = useState(0);

  useEffect(() => {
    let active = true;

    const runCycle = async () => {
      while (active) {
        // Normal EW Green
        setEwLight('green'); setNsLight('red'); setEwBoost(false); setDistActive(false); setSolving(false);
        // Run green normally for enough time for flow to exist
        await new Promise((r) => setTimeout(r, 6000));
        if (!active) break;

        // Trigger a disturbance randomly at the tail end of the normal green cycle
        setDistActive(true);
        // Let ripple build naturally
        await new Promise((r) => setTimeout(r, 2500));
        if (!active) break;

        // Turn on solution / AI intervention — Instead of going yellow, it extends green!
        setSolving(true);
        setEwBoost(true);
        // Hold green for extra time to clear the specific wave
        await new Promise((r) => setTimeout(r, 7000));
        if (!active) break;

        // Clear intervention and transition light
        setDistActive(false);
        setSolving(false);
        setEwBoost(false);

        setEwLight('yellow');
        await new Promise((r) => setTimeout(r, 2000));
        if (!active) break;

        setEwLight('red');
        await new Promise((r) => setTimeout(r, 1000));
        if (!active) break;

        // NS Green 
        setNsLight('green');
        await new Promise((r) => setTimeout(r, 6000));
        if (!active) break;
        setNsLight('yellow');
        await new Promise((r) => setTimeout(r, 2000));
        if (!active) break;
        setNsLight('red');
        await new Promise((r) => setTimeout(r, 1000));
      }
    };
    runCycle();
    return () => { active = false; };
  }, []);

  const asphaltMaterial = useMemo(() => (
    <meshStandardMaterial color="#1c1c1c" roughness={0.9} metalness={0} />
  ), []);
  const sidewalkMaterial = useMemo(() => (
    <meshStandardMaterial color="#242424" roughness={0.8} metalness={0} />
  ), []);
  const solidLineMaterial = useMemo(() => <meshStandardMaterial color="#E8E8E8" emissive="#555555" roughness={0.6} />, []);
  const dashedLineMaterial = useMemo(() => <meshStandardMaterial color="#E8E8E8" emissive="#555555" roughness={0.6} />, []);
  const goldLineMaterial = useMemo(() => <meshStandardMaterial color="#D4AF37" emissive="#5c4f1c" roughness={0.6} />, []);

  // Generate lane markings - optimized with larger dash spacing to reduce mesh count
  const createLaneMarkings = (isVertical) => {
    const lines = [];
    const rot = [-Math.PI / 2, 0, isVertical ? 0 : Math.PI / 2];
    const rWidth = isVertical ? verticalRoadWidth : horizontalRoadWidth;
    const crossWidth = isVertical ? horizontalRoadWidth : verticalRoadWidth;

    // Center divider (gold double line)
    const midOffset = 0.2;
    lines.push(
      <mesh key={`mid1-${isVertical}`} position={[isVertical ? -midOffset : 0, markingYOffset, isVertical ? 0 : -midOffset]} rotation={rot}>
        <planeGeometry args={[0.12, roadLength]} />
        {goldLineMaterial}
      </mesh>,
      <mesh key={`mid2-${isVertical}`} position={[isVertical ? midOffset : 0, markingYOffset, isVertical ? 0 : midOffset]} rotation={rot}>
        <planeGeometry args={[0.12, roadLength]} />
        {goldLineMaterial}
      </mesh>
    );

    // Outer edge lines
    const edgeOffset = rWidth / 2 - 0.3;
    lines.push(
      <mesh key={`edge1-${isVertical}`} position={[isVertical ? -edgeOffset : 0, markingYOffset, isVertical ? 0 : -edgeOffset]} rotation={rot}>
        <planeGeometry args={[0.15, roadLength]} />
        {solidLineMaterial}
      </mesh>,
      <mesh key={`edge2-${isVertical}`} position={[isVertical ? edgeOffset : 0, markingYOffset, isVertical ? 0 : edgeOffset]} rotation={rot}>
        <planeGeometry args={[0.15, roadLength]} />
        {solidLineMaterial}
      </mesh>
    );

    // Dashed lane dividers
    // For vertical road (2 lanes): dashes at ±verticalRoadWidth/4
    // For horizontal road (4 lanes): dashes at ±horizontalRoadWidth/4 (between outer and inner lanes)
    const laneOffsets = isVertical
      ? [rWidth / 4]
      : [rWidth / 4, rWidth * 3 / 8]; // Two sets of dashes for 4-lane road

    // Use larger spacing (every 4 units) to reduce mesh count dramatically
    const dashSpacing = 4;
    const clearance = crossWidth / 2 + 1;

    for (const offset of laneOffsets) {
      for (let i = -roadLength / 2; i <= roadLength / 2; i += dashSpacing) {
        if (Math.abs(i) < clearance) continue;

        lines.push(
          <mesh key={`d1-${isVertical}-${offset}-${i}`} position={[isVertical ? -offset : i, markingYOffset, isVertical ? i : -offset]} rotation={rot}>
            <planeGeometry args={[0.12, 1.5]} />
            {dashedLineMaterial}
          </mesh>,
          <mesh key={`d2-${isVertical}-${offset}-${i}`} position={[isVertical ? offset : i, markingYOffset, isVertical ? i : offset]} rotation={rot}>
            <planeGeometry args={[0.12, 1.5]} />
            {dashedLineMaterial}
          </mesh>
        );
      }
    }

    // Stop lines
    const stopOffsetZ = horizontalRoadWidth / 2 + 1.5;
    const stopOffsetX = verticalRoadWidth / 2 + 1.5;

    if (isVertical) {
      lines.push(
        <mesh key="stop1-v" position={[verticalRoadWidth / 4, markingYOffset, stopOffsetZ]} rotation={[-Math.PI / 2, 0, 0]}>
          <planeGeometry args={[verticalRoadWidth / 2 - 0.3, 0.4]} />
          {solidLineMaterial}
        </mesh>,
        <mesh key="stop2-v" position={[-verticalRoadWidth / 4, markingYOffset, -stopOffsetZ]} rotation={[-Math.PI / 2, 0, 0]}>
          <planeGeometry args={[verticalRoadWidth / 2 - 0.3, 0.4]} />
          {solidLineMaterial}
        </mesh>
      );
    } else {
      lines.push(
        <mesh key="stop1-h" position={[stopOffsetX, markingYOffset, -horizontalRoadWidth / 4]} rotation={[-Math.PI / 2, 0, 0]}>
          <planeGeometry args={[0.4, horizontalRoadWidth / 2 - 0.3]} />
          {solidLineMaterial}
        </mesh>,
        <mesh key="stop2-h" position={[-stopOffsetX, markingYOffset, horizontalRoadWidth / 4]} rotation={[-Math.PI / 2, 0, 0]}>
          <planeGeometry args={[0.4, horizontalRoadWidth / 2 - 0.3]} />
          {solidLineMaterial}
        </mesh>
      );
    }

    return lines;
  };

  const sideWalkSize = 120;
  const cornerOffsetX = verticalRoadWidth / 2 + sideWalkSize / 2;
  const cornerOffsetZ = horizontalRoadWidth / 2 + sideWalkSize / 2;

  return (
    <>
      <ambientLight intensity={0.6} />
      <hemisphereLight skyColor="#ffffff" groundColor="#0a0a0a" intensity={0.8} />
      <directionalLight
        position={[20, 25, -10]}
        intensity={1.2}
        castShadow
        shadow-mapSize-width={2048}
        shadow-mapSize-height={2048}
        shadow-camera-left={-30}
        shadow-camera-right={30}
        shadow-camera-top={30}
        shadow-camera-bottom={-30}
        shadow-bias={-0.0001}
      />

      {/* Ground plane */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.01, 0]} receiveShadow>
        <planeGeometry args={[500, 500]} />
        <meshStandardMaterial color="#0A0A0A" />
      </mesh>

      {/* Vertical Road */}
      <mesh receiveShadow castShadow position={[0, roadYOffset, 0]}>
        <boxGeometry args={[verticalRoadWidth, roadThickness, roadLength]} />
        {asphaltMaterial}
      </mesh>
      {/* Horizontal Hero Road (4 lanes wide) */}
      <mesh receiveShadow castShadow position={[0, roadYOffset, 0]}>
        <boxGeometry args={[roadLength, roadThickness, horizontalRoadWidth]} />
        {asphaltMaterial}
      </mesh>

      {/* Center patch */}
      <mesh position={[0, roadYOffset + roadThickness / 2 + 0.001, 0]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[verticalRoadWidth - 0.5, horizontalRoadWidth - 0.5]} />
        <meshStandardMaterial color="#1c1c1c" roughness={1} metalness={0} />
      </mesh>

      {/* Sidewalks */}
      <mesh receiveShadow castShadow position={[cornerOffsetX, 0.2, cornerOffsetZ]}>
        <boxGeometry args={[sideWalkSize, 0.4, sideWalkSize]} />
        {sidewalkMaterial}
      </mesh>
      <mesh receiveShadow castShadow position={[cornerOffsetX, 0.2, -cornerOffsetZ]}>
        <boxGeometry args={[sideWalkSize, 0.4, sideWalkSize]} />
        {sidewalkMaterial}
      </mesh>
      <mesh receiveShadow castShadow position={[-cornerOffsetX, 0.2, cornerOffsetZ]}>
        <boxGeometry args={[sideWalkSize, 0.4, sideWalkSize]} />
        {sidewalkMaterial}
      </mesh>
      <mesh receiveShadow castShadow position={[-cornerOffsetX, 0.2, -cornerOffsetZ]}>
        <boxGeometry args={[sideWalkSize, 0.4, sideWalkSize]} />
        {sidewalkMaterial}
      </mesh>

      {/* Road markings */}
      {createLaneMarkings(true)}
      {createLaneMarkings(false)}

      {/* Traffic Signals at each corner */}
      <TrafficSignal position={[verticalRoadWidth / 2 + 0.6, 0.4, horizontalRoadWidth / 2 + 0.6]} rotation={[0, Math.PI, 0]} state={nsLight} />
      <TrafficSignal position={[-verticalRoadWidth / 2 - 0.6, 0.4, -horizontalRoadWidth / 2 - 0.6]} rotation={[0, 0, 0]} state={nsLight} />
      <TrafficSignal position={[-verticalRoadWidth / 2 - 0.6, 0.4, horizontalRoadWidth / 2 + 0.6]} rotation={[0, -Math.PI / 2, 0]} state={ewLight} boost={ewBoost} />
      <TrafficSignal position={[verticalRoadWidth / 2 + 0.6, 0.4, -horizontalRoadWidth / 2 - 0.6]} rotation={[0, Math.PI / 2, 0]} state={ewLight} boost={ewBoost} />

      {/* Vehicles */}
      <SolutionVehicles3D nsLight={nsLight} ewLight={ewLight} distActive={distActive} solving={solving} />
    </>
  );
}