import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Sparkles, X, ChevronLeft, ChevronRight, BookOpen, Settings, Play, Info, Search, Minimize2, Maximize2, Pin, PinOff,
  Zap, TrendingUp, Lightbulb, Eye, LineChart, Cpu, ChevronUp, ChevronDown
} from 'lucide-react';
import { useAssetStore } from '../../store/assetStore';
import { useAuthStore } from '../../store/useAuthStore';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { getAllExamples } from '../examples/registry/exampleRegistry';
import { loadExample } from '../examples/loader/loadExample';
import type { SandboxRuntime } from '../engine/runtime';
import type { RuntimeObject } from '../types/RuntimeObject';
import Matter, { type Body } from 'matter-js';
import { ConstraintRegistry } from '../constraints/constraintRegistry';
import type { ConstraintRenderer } from '../constraints/constraintRenderer';
import type { GravityRenderer } from '../gravity/gravityRenderer';
import { ObservableEngine } from '../observables/observableEngine';
import { RuntimeStore } from '../state/runtimeStore';
import { PropertyController } from '../properties/propertyController';
import { PropertyPanel } from '../ui/PropertyPanel';
import { RuntimeObserver } from '../../ai/runtimeObserver';
import { useExplanationEngine } from '../../ai/explanationEngine';
import { FloatingAssetPanel } from '../../components/AssetLibrary/FloatingAssetPanel';
import { physicsEventBus } from '../../ai/physicsEventBus';

import { useGuidedModeStore } from '../../store/guidedModeStore';
import { InteractiveGuideModal } from './InteractiveGuideModal';
import { BuildGuidePanel } from './BuildGuidePanel';
import { SandboxValidationState } from '../utils/guidedValidation';
import { getApiUrl } from '../../config/api';
import { useSimulationStore } from '../../store/useSimulationStore';


// ─── Constants ────────────────────────────────────────────────────────────────

type GravityPreset = 'zero' | 'moon' | 'earth' | 'jupiter' | 'custom';

const GRAVITY_VALUES: Record<Exclude<GravityPreset, 'custom'>, number> = {
  zero: 0, moon: 0.16, earth: 1, jupiter: 2.53,
};

const PALETTE = [
  { fill: 0x4F8EF7, stroke: 0x2563EB }, // Blue #4F8EF7
  { fill: 0x22C55E, stroke: 0x16A34A }, // Green #22C55E
  { fill: 0xF97316, stroke: 0xEA580C }, // Orange #F97316
  { fill: 0xA855F7, stroke: 0x9333EA }, // Purple #A855F7
  { fill: 0x38BDF8, stroke: 0x0284C7 }, // Sky
  { fill: 0xFBBF24, stroke: 0xD97706 }, // Amber
  { fill: 0xEC4899, stroke: 0xDB2777 }, // Pink
  { fill: 0x6366F1, stroke: 0x4F46E5 }, // Indigo
];

let _pi = 0;
let _uid = 0;
const nextColour = () => PALETTE[_pi++ % PALETTE.length];
const uid = (p: string) => `${p}-${++_uid}`;

// ─── Stable refs ─────────────────────────────────────────────────────────────

interface InteractionRefs {
  drag: import('../interactions/drag').DragController;
  selection: import('../interactions/selection').SelectionManager;
  controls: import('../interactions/controls').RuntimeControls;
}

// ─── Scene builder ────────────────────────────────────────────────────────────

async function buildScene(
  rt: SandboxRuntime,
  el: HTMLElement,
  interactions: InteractionRefs,
  constraintReg: ConstraintRegistry,
  store: RuntimeStore,
): Promise<Body[]> {
  const { createObject } = await import('../objects/objectFactory');
  const { createConstraint } = await import('../constraints/constraintFactory');

  rt.physics.clear(false);
  rt.sync.clear();
  constraintReg.clear();          // remove old constraints from world
  interactions.selection.clear();
  _uid = 0; _pi = 0;

  const vp = rt.renderer.getViewport();
  // Remove non-graphics children, while preserving constraint and observable overlays.
  for (let i = vp.children.length - 1; i >= 0; i--) {
    const child = vp.children[i];
    const meta = child as { _isConstraintOverlay?: boolean; _isObservableOverlay?: boolean; _isGravityOverlay?: boolean };
    if (meta._isConstraintOverlay || meta._isObservableOverlay || meta._isGravityOverlay) continue;
    vp.removeChildAt(i);
  }

  vp.eventMode = 'passive';

  const W = el.clientWidth || 800;
  const H = el.clientHeight || 600;
  const dynamic: Body[] = [];

  const addStatic = (obj: RuntimeObject) => {
    vp.addChild(obj.display);
    rt.physics.addBodies(obj.body);
    rt.sync.register(obj.id, obj.body, obj.display);
    store.addObject(obj);
  };

  const addDynamic = (obj: RuntimeObject) => {
    vp.addChild(obj.display);
    rt.physics.addBodies(obj.body);
    rt.sync.register(obj.id, obj.body, obj.display);
    interactions.selection.register(obj);
    store.addObject(obj);
    dynamic.push(obj.body);
  };

  const addConstraint = (cfg: Parameters<typeof createConstraint>[0]) => {
    constraintReg.add(createConstraint(cfg));
  };

  // ── Static boundaries ─────────────────────────────────────────────────────
  addStatic(createObject({
    id: 'ground', type: 'rectangle',
    x: W / 2, y: H - 124, width: 5000, height: 28,
    isStatic: true, fillColor: 0x4F8EF7, strokeColor: 0x2563eb, strokeWidth: 2.5,
  }));
  addStatic(createObject({
    id: 'wall-l', type: 'rectangle',
    x: -8, y: H / 2, width: 16, height: 5000,
    isStatic: true, fillColor: 0x4F8EF7, strokeColor: 0x2563eb, strokeWidth: 2.5,
  }));
  addStatic(createObject({
    id: 'wall-r', type: 'rectangle',
    x: W + 8, y: H / 2, width: 16, height: 5000,
    isStatic: true, fillColor: 0x4F8EF7, strokeColor: 0x2563eb, strokeWidth: 2.5,
  }));
  addStatic(createObject({
    id: 'wall-t', type: 'rectangle',
    x: W / 2, y: -8, width: 5000, height: 16,
    isStatic: true, fillColor: 0x4F8EF7, strokeColor: 0x2563eb, strokeWidth: 2.5,
  }));

  return dynamic;
}

// ─── AI Response Parser & UI Components ───────────────────────────────────────

const parseExplanationText = (text: string) => {
  const sections: Record<string, string> = {};
  if (!text) return sections;

  // Standard split by markdown headers
  const parts = text.split(/(?=###\s*✦?\s*)/gi);
  for (const part of parts) {
    const trimmed = part.trim();
    if (!trimmed) continue;

    // Match ### ✦ NAME or ### NAME
    const match = trimmed.match(/^###\s*✦?\s*([^\n]+)/i);
    if (match) {
      const title = match[1].trim().toUpperCase();
      const content = trimmed.substring(match[0].length).trim();
      sections[title] = content;
    }
  }
  return sections;
};

interface StepCardProps {
  num: number;
  title: string;
  description: string;
  type: 'blue' | 'green' | 'orange' | 'purple';
}

const StepCard: React.FC<StepCardProps> = ({ num, title, description, type }) => {
  const isBlue = type === 'blue';
  const isGreen = type === 'green';
  const isOrange = type === 'orange';

  let glowColor = 'rgba(168, 85, 247, 0.35)';
  let iconBg = 'rgba(168, 85, 247, 0.2)';
  let iconColor = '#c084fc';

  if (isBlue) {
    glowColor = 'rgba(14, 165, 233, 0.35)';
    iconBg = 'rgba(14, 165, 233, 0.2)';
    iconColor = '#38bdf8';
  } else if (isGreen) {
    glowColor = 'rgba(16, 185, 129, 0.35)';
    iconBg = 'rgba(16, 185, 129, 0.2)';
    iconColor = '#34d399';
  } else if (isOrange) {
    glowColor = 'rgba(245, 158, 11, 0.35)';
    iconBg = 'rgba(245, 158, 11, 0.2)';
    iconColor = '#fbbf24';
  }

  const formattedTitle = num === 1 ? '1. What Happened'
    : num === 2 ? '2. What Changed'
      : num === 3 ? '3. Simple Why'
        : '4. What to Notice';

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      style={{
        display: 'flex',
        gap: 16,
        padding: '12px 0',
        alignItems: 'flex-start',
        borderBottom: num < 4 ? '1px solid rgba(255, 255, 255, 0.05)' : 'none',
      }}
    >
      <div style={{
        width: 38,
        height: 38,
        borderRadius: '50%',
        background: iconBg,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        boxShadow: `0 0 12px ${glowColor}`,
        flexShrink: 0,
        marginTop: 1,
        border: `1px solid ${iconColor}33`
      }}>
        {isBlue && <Sparkles size={18} color={iconColor} />}
        {isGreen && (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={iconColor} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="2" fill={iconColor} />
            <line x1="12" y1="12" x2="6" y2="6" />
            <path d="M6 10V6H10" />
            <line x1="12" y1="12" x2="18" y2="6" />
            <path d="M14 6H18V10" />
            <line x1="12" y1="12" x2="6" y2="18" />
            <path d="M6 14V18H10" />
            <line x1="12" y1="12" x2="18" y2="18" />
            <path d="M14 18H18V14" />
          </svg>
        )}
        {isOrange && <Lightbulb size={18} color={iconColor} />}
        {type === 'purple' && <Eye size={18} color={iconColor} />}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, flex: 1 }}>
        <span style={{
          fontSize: 13.5,
          fontWeight: 700,
          color: iconColor,
          fontFamily: "'Plus Jakarta Sans', system-ui, sans-serif"
        }}>
          {formattedTitle}
        </span>
        <div style={{
          fontSize: 12,
          color: '#cbd5e1',
          lineHeight: 1.55,
          fontWeight: 500
        }}>
          <ReactMarkdown
            remarkPlugins={[remarkMath]}
            rehypePlugins={[rehypeKatex]}
            components={{
              p: ({ node, ...props }: any) => <p style={{ margin: 0 }} {...props} />,
              code: ({ node, inline, ...props }: any) => (
                <code style={{
                  background: 'rgba(255,255,255,0.08)',
                  padding: '2px 4px',
                  borderRadius: 4,
                  fontSize: '0.85em',
                  fontFamily: 'monospace',
                  color: '#e9d5ff'
                }} {...props} />
              )
            }}
          >
            {description}
          </ReactMarkdown>
        </div>
      </div>
    </motion.div>
  );
};

// ─── Component ────────────────────────────────────────────────────────────────

export const SandboxCanvas: React.FC = () => {
  const { mode, isOpen, activeStep, guideData, highlightedAsset, setIsOpen, setActiveStep } = useGuidedModeStore();
  const { isMaximized, setMaximized } = useSimulationStore();

  const mountRef = useRef<HTMLDivElement>(null);
  const runtimeRef = useRef<SandboxRuntime | null>(null);
  const storeRef = useRef<RuntimeStore | null>(null);
  const interactionRef = useRef<InteractionRefs | null>(null);
  const constraintRegRef = useRef<ConstraintRegistry | null>(null);
  const constraintRenRef = useRef<ConstraintRenderer | null>(null);
  const gravityRenRef = useRef<GravityRenderer | null>(null);
  const observableEngineRef = useRef<ObservableEngine | null>(null);
  const dynRef = useRef<Body[]>([]);

  const [running, setRunning] = useState(false);
  const [leftPanelOpen, setLeftPanelOpen] = useState(() => typeof window !== 'undefined' ? window.innerWidth >= 1024 : true);
  const [rightPanelOpen, setRightPanelOpen] = useState(() => typeof window !== 'undefined' ? window.innerWidth >= 1024 : true);
  const [ready, setReady] = useState(false);
  const [bodyCount, setBodyCount] = useState(0);
  const [gravity, setGravity] = useState<GravityPreset>('earth');
  const [gravityValue, setGravityValue] = useState<number>(1.0);
  const [speed, setSpeed] = useState(1);
  const [selected, setSelected] = useState<RuntimeObject | null>(null);
  const [tutorEnabled, setTutorEnabled] = useState(true);
  const [dynamicExplanationEnabled, setDynamicExplanationEnabled] = useState(false);
  const [tutorWidth, setTutorWidth] = useState(380);
  const [tutorHeight, setTutorHeight] = useState(500);
  const [tutorMinimized, setTutorMinimized] = useState(false);
  const [tutorPinned, setTutorPinned] = useState(false);
  const [tutorMaximized, setTutorMaximized] = useState(false);
  const [activeTab, setActiveTab] = useState<'explanation' | 'effects' | 'formula'>('explanation');
  const [gravityMode, setGravityMode] = useState<'linear' | 'radial'>('linear');
  const [boundaryMode, setBoundaryMode] = useState<'screen' | 'custom' | 'none'>('screen');
  const [customWidth, setCustomWidth] = useState(1200);
  const [customHeight, setCustomHeight] = useState(800);
  const [boundaryThickness] = useState(28);
  const [propertyVersion, setPropertyVersion] = useState(0);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth < 1024);
    };
    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const boundaryModeRef = useRef(boundaryMode);
  const customWidthRef = useRef(customWidth);
  const customHeightRef = useRef(customHeight);
  const gravityModeRef = useRef(gravityMode);

  useEffect(() => { boundaryModeRef.current = boundaryMode; }, [boundaryMode]);
  useEffect(() => { customWidthRef.current = customWidth; }, [customWidth]);
  useEffect(() => { customHeightRef.current = customHeight; }, [customHeight]);
  useEffect(() => { gravityModeRef.current = gravityMode; }, [gravityMode]);

  const repositionBoundaries = useCallback(async (
    W: number,
    H: number,
    currentZoom: number = zoomRef.current,
    currentPanX: number = panXRef.current,
    currentPanY: number = panYRef.current
  ) => {
    const store = storeRef.current;
    if (!store) return;

    const Matter = await import('matter-js');
    const ground = store.getObject('ground');
    const wallL = store.getObject('wall-l');
    const wallR = store.getObject('wall-r');
    const wallT = store.getObject('wall-t');

    const mode = boundaryModeRef.current;
    const cW = customWidthRef.current;
    const cH = customHeightRef.current;
    const thickness = boundaryThickness;
    const isRadial = gravityModeRef.current === 'radial';

    // 1. Calculate the active boundary positions in the baseline world space
    let targetGround = { x: W / 2, y: H - 40, width: 5000, height: thickness, visible: true, collides: true };
    let targetWallL = { x: -8, y: H / 2, width: 16, height: 5000, visible: false, collides: true };
    let targetWallR = { x: W + 8, y: H / 2, width: 16, height: 5000, visible: false, collides: true };
    let targetWallT = { x: W / 2, y: -8, width: 5000, height: 16, visible: false, collides: true };

    if (mode === 'none' || isRadial) {
      // Disable collisions and hide
      targetGround.collides = false; targetGround.visible = false;
      targetWallL.collides = false; targetWallL.visible = false;
      targetWallR.collides = false; targetWallR.visible = false;
      targetWallT.collides = false; targetWallT.visible = false;
    } else if (mode === 'screen') {
      // Dynamic: Locked to screen edges in world space
      const minX = -currentPanX / currentZoom;
      const maxX = (W - currentPanX) / currentZoom;
      const minY = -currentPanY / currentZoom;
      const maxY = (H - currentPanY) / currentZoom;

      // Ground (at bottom edge of screen)
      targetGround.x = (minX + maxX) / 2;
      targetGround.y = maxY - thickness / 2;
      targetGround.width = maxX - minX + 1000;
      targetGround.visible = true;

      // Left Wall
      targetWallL.x = minX + 8;
      targetWallL.y = (minY + maxY) / 2;
      targetWallL.height = maxY - minY + 1000;
      targetWallL.visible = true;

      // Right Wall
      targetWallR.x = maxX - 8;
      targetWallR.y = (minY + maxY) / 2;
      targetWallR.height = maxY - minY + 1000;
      targetWallR.visible = true;

      // Top Wall (Ceiling)
      targetWallT.x = (minX + maxX) / 2;
      targetWallT.y = minY + 8;
      targetWallT.width = maxX - minX + 1000;
      targetWallT.visible = true;
    } else if (mode === 'custom') {
      // Center the custom box in baseline world space
      const centerX = W / 2;
      const centerY = H / 2;
      const minX = centerX - cW / 2;
      const maxX = centerX + cW / 2;
      const minY = centerY - cH / 2;
      const maxY = centerY + cH / 2;

      targetGround.x = centerX;
      targetGround.y = maxY - thickness / 2;
      targetGround.width = cW;
      targetGround.visible = true;

      targetWallL.x = minX + 8;
      targetWallL.y = centerY;
      targetWallL.height = cH;
      targetWallL.visible = true;

      targetWallR.x = maxX - 8;
      targetWallR.y = centerY;
      targetWallR.height = cH;
      targetWallR.visible = true;

      targetWallT.x = centerX;
      targetWallT.y = minY + 8;
      targetWallT.width = cW;
      targetWallT.visible = true;
    }

    // 2. Apply updates to the Matter.js bodies and PixiJS graphics
    const updateBodyAndDisplay = (obj: any, target: typeof targetGround) => {
      if (!obj) return;

      // Update Matter body
      Matter.Body.setPosition(obj.body, { x: target.x, y: target.y });

      // Update collision filter
      obj.body.collisionFilter.category = target.collides ? 0x0001 : 0x0000;
      obj.body.collisionFilter.mask = target.collides ? 0xFFFF : 0x0000;

      // Update Pixi display
      obj.display.x = target.x;
      obj.display.y = target.y;
      obj.display.visible = target.visible;

      if (obj.body.parts && obj.body.parts[0]) {
        if (obj.display.children && obj.display.children[0]) {
          const gfx = obj.display.children[0];
          if (obj.id === 'ground') {
            gfx.scale.x = target.width / 5000;
            gfx.alpha = target.visible ? 0.95 : 0;
          } else if (obj.id === 'wall-l' || obj.id === 'wall-r') {
            gfx.scale.y = target.height / 5000;
            gfx.alpha = target.visible ? 0.65 : 0;
          } else if (obj.id === 'wall-t') {
            gfx.scale.x = target.width / 5000;
            gfx.alpha = target.visible ? 0.65 : 0;
          }
        }
      }
    };

    updateBodyAndDisplay(ground, targetGround);
    updateBodyAndDisplay(wallL, targetWallL);
    updateBodyAndDisplay(wallR, targetWallR);
    updateBodyAndDisplay(wallT, targetWallT);

    // Force PIXI rendering tick
    const rt = runtimeRef.current;
    if (rt) {
      rt.renderer.getApp().render();
    }
  }, [boundaryThickness]);


  // Memoized sandbox validation state to prevent excessive recalculations and infinite render loops in guide panels
  const currentValidationState = useMemo<SandboxValidationState>(() => {
    return {
      bodies: storeRef.current ? storeRef.current.getAllObjects().map(o => ({
        id: o.id,
        isStatic: o.body.isStatic,
        mass: o.body.mass,
        velocity: o.body.velocity,
      })) : [],
      constraints: constraintRegRef.current ? constraintRegRef.current.getAll().map(c => ({
        id: c.id,
        type: c.type,
      })) : [],
      gravityMode: gravityMode,
      gravityPreset: gravity,
      running: running,
    };
  }, [ready, bodyCount, propertyVersion, gravityMode, gravity, running]);

  const handleResizeLeft = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    const startX = e.clientX;
    const startWidth = tutorWidth;

    const onPointerMove = (moveEvent: PointerEvent) => {
      const newWidth = Math.max(280, Math.min(800, startWidth + (startX - moveEvent.clientX)));
      setTutorWidth(newWidth);
    };

    const onPointerUp = () => {
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerup', onPointerUp);
    };

    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', onPointerUp);
  }, [tutorWidth]);

  const handleResizeBottom = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    const startY = e.clientY;
    const startHeight = tutorHeight;

    const onPointerMove = (moveEvent: PointerEvent) => {
      const newHeight = Math.max(200, Math.min(900, startHeight + (moveEvent.clientY - startY)));
      setTutorHeight(newHeight);
    };

    const onPointerUp = () => {
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerup', onPointerUp);
    };

    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', onPointerUp);
  }, [tutorHeight]);

  const handleResizeBottomLeft = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    const startX = e.clientX;
    const startY = e.clientY;
    const startWidth = tutorWidth;
    const startHeight = tutorHeight;

    const onPointerMove = (moveEvent: PointerEvent) => {
      const newWidth = Math.max(280, Math.min(800, startWidth + (startX - moveEvent.clientX)));
      const newHeight = Math.max(200, Math.min(900, startHeight + (moveEvent.clientY - startY)));
      setTutorWidth(newWidth);
      setTutorHeight(newHeight);
    };

    const onPointerUp = () => {
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerup', onPointerUp);
    };

    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', onPointerUp);
  }, [tutorWidth, tutorHeight]);

  // Modular Switchable Gravity System states
  const [gConstant, setGConstant] = useState(0.0012);
  const [radialDebug, setRadialDebug] = useState(true);

  // Textbook Examples Panel States
  const [activeLeftTab, setActiveLeftTab] = useState<'toolbox' | 'examples'>('toolbox');
  const [selectedExampleId, setSelectedExampleId] = useState<string | null>(null);
  const [exampleSearch, setExampleSearch] = useState('');

  // Viewport Camera states
  const [zoom, setZoom] = useState(1.0);
  const [panX, setPanX] = useState(0);
  const [panY, setPanY] = useState(0);

  const zoomRef = useRef(1.0);
  const panXRef = useRef(0);
  const panYRef = useRef(0);

  useEffect(() => { zoomRef.current = zoom; }, [zoom]);
  useEffect(() => { panXRef.current = panX; }, [panX]);
  useEffect(() => { panYRef.current = panY; }, [panY]);

  const spacePressedRef = useRef(false);
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.code === 'Space') {
        spacePressedRef.current = true;
        const canvas = runtimeRef.current?.renderer.getApp().canvas as HTMLCanvasElement;
        if (canvas && canvas.style.cursor === 'default') {
          canvas.style.cursor = 'grab';
        }
      }
    };
    const handleKeyUp = (e: KeyboardEvent) => {
      if (e.code === 'Space') {
        spacePressedRef.current = false;
        const canvas = runtimeRef.current?.renderer.getApp().canvas as HTMLCanvasElement;
        if (canvas && canvas.style.cursor === 'grab') {
          canvas.style.cursor = 'default';
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, []);

  const [aiPrompt, setAiPrompt] = useState("");
  const [aiLoading, setAiLoading] = useState(false);
  const [aiResponse, setAiResponse] = useState<string | null>(null);
  const [showAiPanel, setShowAiPanel] = useState(false);

  const activeExample = selectedExampleId ? getAllExamples().find(ex => ex.id === selectedExampleId) : null;
  const activeExampleName = activeExample?.title || undefined;
  const activeExampleDescription = activeExample?.description || undefined;

  const { currentExplanation, queueCount, handleDismiss, setIsHovered, pushExplanation, handleNext, handleClear } = useExplanationEngine(
    tutorEnabled,
    gravityMode,
    activeExampleName,
    activeExampleDescription
  );
  const handleAiQuery = async (queryOverride?: string) => {
    const queryToUse = queryOverride !== undefined ? queryOverride : aiPrompt;
    if (!queryToUse.trim()) return;
    setAiLoading(true);
    setTutorEnabled(true);

    // Clear previous AI asset suggestions on every new query
    useAssetStore.getState().clearSuggestedAssets();

    try {
      const token = useAuthStore.getState().token;
      const headers: Record<string, string> = {
        'Content-Type': 'application/json'
      };
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      // ── Fire calls in parallel ────────────────────────────────────────
      const [sceneResp, guideResp] = await Promise.allSettled([
        // 1. Scene parser call
        fetch(getApiUrl('/api/scene/parse'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_input: queryToUse })
        }),
        // 2. Dedicated guide/instructions call
        fetch(getApiUrl('/api/tutor/guide'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: queryToUse })
        })
      ]);

      // ── Handle guide response ──────────────────────────────────────────────
      if (guideResp && guideResp.status === 'fulfilled') {
        const resp = guideResp.value;
        if (resp.ok) {
          const json = await resp.json();
          if (json.success && json.data) {
            const d = json.data;
            const guide = d.simulation_guide;
            if (guide && (guide.is_buildable || (Array.isArray(guide.steps) && guide.steps.length > 0))) {
              useGuidedModeStore.setState({
                mode: 'guided',
                guideData: guide,
                isOpen: true,
                activeStep: 1,
                completedSteps: [],
                highlightedAsset: null,
                showMeOverlay: null
              });
            }
          }
        }
      }

      // ── Handle scene parse response ────────────────────────────────────────
      if (sceneResp.status === 'fulfilled') {
        try {
          const sceneJson = await sceneResp.value.json();
          if (sceneJson.success && sceneJson.data) {
            const scene = sceneJson.data;
            const assets: string[] = scene.recommended_assets || [];
            const topic: string = scene.topic || '';
            if (assets.length > 0) {
              useAssetStore.getState().setSuggestedAssets(assets, topic);
            }
          }
        } catch (_) {
          // Non-critical — scene parse failure doesn't break the tutor UX
          console.warn('[SceneParser] Failed to parse scene response');
        }
      }

    } catch (e) {
      pushExplanation({
        title: 'Connection Error',
        explanation: (e as Error).message,
        effects: ['Ensure the EduSim API is running on port 8001'],
        formula: '',
        suggestions: []
      });
    } finally {
      setAiLoading(false);
      setAiPrompt('');
    }
  };

  useEffect(() => {
    if (ready) {
      const params = new URLSearchParams(window.location.search);
      const queryParam = params.get('query');
      if (queryParam) {
        handleAiQuery(queryParam);
        const newUrl = window.location.pathname;
        window.history.replaceState({}, '', newUrl);
      }
    }
  }, [ready]);


  const handleAiKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleAiQuery();
    }
  };

  const handleAutoBuild = useCallback(async (spawnConfig: any) => {
    const rt = runtimeRef.current;
    const ia = interactionRef.current;
    const creg = constraintRegRef.current;
    const store = storeRef.current;
    const el = mountRef.current;
    if (!rt || !ia || !creg || !el || !store || !ready) return;

    // Pausing simulation clock and clearing canvas state
    rt.pause();
    store.reset();
    simTimeRef.current = 0;

    // Dynamic clean elements
    const burnOverlay = document.getElementById('example-burn-overlay');
    if (burnOverlay) burnOverlay.remove();
    const energyOverlay = document.getElementById('example-energy-overlay');
    if (energyOverlay) energyOverlay.remove();

    // Rebuild standard borders
    const dyn = await buildScene(rt, el, ia, creg, store);
    dynRef.current = dyn;
    setBodyCount(dyn.length);
    setSelected(null);

    // Spawn custom bodies
    const { createObject } = await import('../objects/objectFactory');
    const spawnedBodiesMap = new Map<string, any>();

    if (spawnConfig.bodies && Array.isArray(spawnConfig.bodies)) {
      const uidCount: Record<string, number> = {};
      const getUniqueId = (prefix: string) => {
        uidCount[prefix] = (uidCount[prefix] || 0) + 1;
        return `${prefix}-${uidCount[prefix]}-${Math.random().toString(36).substr(2, 4)}`;
      };

      for (const bodyCfg of spawnConfig.bodies) {
        const type = bodyCfg.type || 'circle';
        const isStatic = bodyCfg.isStatic ?? false;
        const rest = bodyCfg.restitution ?? 0.6;
        const fillString = bodyCfg.fillColor || '0x6366f1';
        const fillColor = parseInt(fillString.replace('0x', ''), 16);

        const base = {
          x: bodyCfg.x,
          y: bodyCfg.y,
          restitution: rest,
          friction: 0.1,
          density: 0.002,
          isStatic,
          fillColor,
          strokeColor: fillColor,
          strokeWidth: 2.5
        };

        const obj = type === 'circle'
          ? createObject({
            id: bodyCfg.id || getUniqueId('circle'),
            type: 'circle',
            radius: bodyCfg.radius || 20,
            ...base
          })
          : createObject({
            id: bodyCfg.id || getUniqueId('rect'),
            type: 'rectangle',
            width: bodyCfg.width || 40,
            height: bodyCfg.height || 40,
            cornerRadius: 8,
            ...base
          });

        // Set custom mass if explicitly asked by the tutor config
        if (bodyCfg.mass !== undefined && obj.body) {
          const Matter = await import('matter-js');
          Matter.Body.setMass(obj.body, bodyCfg.mass);
        }

        rt.renderer.getViewport().addChild(obj.display);
        rt.physics.addBodies(obj.body);
        rt.sync.register(obj.id, obj.body, obj.display);
        ia.selection.register(obj);
        store.addObject(obj);
        dynRef.current.push(obj.body);

        spawnedBodiesMap.set(bodyCfg.id, obj);
      }
      setBodyCount(dynRef.current.length);
    }

    // Spawn custom constraints
    if (spawnConfig.constraints && Array.isArray(spawnConfig.constraints)) {
      const { createConstraint } = await import('../constraints/constraintFactory');
      const constUidCount: Record<string, number> = {};
      const getUniqueConstId = (prefix: string) => {
        constUidCount[prefix] = (constUidCount[prefix] || 0) + 1;
        return `${prefix}-${constUidCount[prefix]}`;
      };

      for (const constCfg of spawnConfig.constraints) {
        const type = constCfg.type || 'rope';
        const bodyAObj = spawnedBodiesMap.get(constCfg.bodyIdA);
        const bodyBObj = spawnedBodiesMap.get(constCfg.bodyIdB);
        if (!bodyAObj || !bodyBObj) continue;

        const stiffness = constCfg.stiffness ?? (type === 'spring' ? 0.02 : 0.9);
        const damping = constCfg.damping ?? 0.01;
        const length = constCfg.length ?? Math.hypot(
          bodyAObj.body.position.x - bodyBObj.body.position.x,
          bodyAObj.body.position.y - bodyBObj.body.position.y
        );

        creg.add(createConstraint({
          id: constCfg.id || getUniqueConstId('constraint'),
          type: type as any,
          bodyA: bodyAObj.body,
          bodyB: bodyBObj.body,
          length,
          stiffness,
          damping
        }));
      }
    }

    // Set gravity preset
    if (spawnConfig.gravityPreset) {
      changeGravity(spawnConfig.gravityPreset);
    }
    if (spawnConfig.gravityMode) {
      handleModeChange(spawnConfig.gravityMode);
    }

    // Apply initial forces
    if (spawnConfig.forces && Array.isArray(spawnConfig.forces)) {
      const Matter = await import('matter-js');
      for (const forceCfg of spawnConfig.forces) {
        const bodyObj = spawnedBodiesMap.get(forceCfg.bodyId);
        if (bodyObj && forceCfg.vector) {
          Matter.Body.applyForce(bodyObj.body, bodyObj.body.position, forceCfg.vector);
        }
      }
    }

    // Always pause simulation on auto-build start so student can inspect
    rt.pause();
    store.setRuntimeState('paused');
    setRunning(false);
  }, [ready, changeGravity, handleModeChange]);

  const propertyControllerRef = useRef<PropertyController | null>(null);
  const observerRef = useRef<RuntimeObserver | null>(null);

  const [telemetryTick, setTelemetryTick] = useState(0);
  const simTimeRef = useRef(0);
  const [bottomPanelOpen, setBottomPanelOpen] = useState(true);

  // Initialize runtime observer once ready
  useEffect(() => {
    if (ready && storeRef.current && propertyControllerRef.current && runtimeRef.current && !observerRef.current) {
      observerRef.current = new RuntimeObserver(
        storeRef.current,
        propertyControllerRef.current,
        runtimeRef.current
      );
      observerRef.current.start();
    }
    return () => {
      if (observerRef.current) {
        observerRef.current.stop();
        observerRef.current = null;
      }
    };
  }, [ready]);

  // Synchronize pin state with tutor auto-dismiss timer by setting isHovered
  useEffect(() => {
    setIsHovered(tutorPinned);
  }, [tutorPinned, setIsHovered]);



  // Panel drag-and-drop state
  type PanelDragType = 'circle' | 'rectangle' | 'pendulum-rope' | 'pivot' | 'spring' | 'rope' | 'sun' | 'planet' | null;
  const panelDragRef = useRef<PanelDragType>(null);          // type being dragged
  const didDragRef = useRef(false);                        // suppresses onClick after a real drag
  const hoveredBodyRef = useRef<Body | null>(null);
  const [hoveredBodyId, setHoveredBodyId] = useState<string | null>(null);
  const [ghostPos, setGhostPos] = useState({ x: -999, y: -999 });
  const [isDragging, setIsDragging] = useState(false);
  const [isOverCanvas, setIsOverCanvas] = useState(false);

  // Check and snap a physics body to any nearby unconnected constraint receptors
  const checkConstraintSnapping = useCallback(async (newBody: Body) => {
    const rt = runtimeRef.current;
    const creg = constraintRegRef.current;
    if (!rt || !creg) return;

    const allBodies = rt.physics.getWorld().bodies;
    const sensors = allBodies.filter((b: any) => b.label && b.label.startsWith('sensor-target:'));

    for (const sensor of sensors) {
      const dist = Math.hypot(newBody.position.x - sensor.position.x, newBody.position.y - sensor.position.y);
      if (dist < 100) { // generous snap tolerance so user can drop anywhere near the bottom of the rope
        const parts = sensor.label.split(':');
        const constraintId = parts[1];
        const syncDisplayId = parts[2]; // populated by spawnPendulumRope for its visible drop-zone
        const rc = creg.getAll().find(c => c.id === constraintId);
        if (rc) {
          // Relink constraint from temporary sensor bob to real dropped shape
          if (rc.constraint.bodyB === sensor) {
            rc.constraint.bodyB = newBody;
            if (rc.type === 'pivot') {
              const newDist = Math.hypot(rc.constraint.bodyA!.position.x - newBody.position.x, rc.constraint.bodyA!.position.y - newBody.position.y);
              rc.constraint.length = newDist;
            }
          } else if (rc.constraint.bodyA === sensor) {
            rc.constraint.bodyA = newBody;
          }

          // Remove physics sensor body
          rt.physics.removeBodies(sensor);

          // Remove the visible drop-zone display that was synced to the sensor
          if (syncDisplayId) {
            const pair = rt.sync.getPairs().get(syncDisplayId);
            if (pair) {
              pair.displayObject.parent?.removeChild(pair.displayObject);
              pair.displayObject.destroy();
              rt.sync.unregister(syncDisplayId);
            }
          }

          break;
        }
      }
    }
  }, []);

  const stabilizeDraggedCelestial = useCallback(async (body: Body) => {
    const rt = runtimeRef.current;
    const store = storeRef.current;
    const customData = (body as any).customData;
    if (!rt || !store || !customData?.celestialConfig) return;

    const config = customData.celestialConfig;
    const virtualMass = customData.mass ?? body.mass;
    const canvasX = body.position.x;
    const canvasY = body.position.y;

    const radialGravity = rt.gravitySystem.getRadialGravity();
    const activeSources = radialGravity.getSources();

    let parentSource = null;
    let minDist = Infinity;

    for (const src of activeSources) {
      if (src.id === (body as any).objectId) continue;
      const dist = Math.hypot(src.position.x - canvasX, src.position.y - canvasY);
      if (src.mass > virtualMass && dist < minDist) {
        minDist = dist;
        parentSource = src;
      }
    }

    if (!parentSource) {
      for (const src of activeSources) {
        if (src.id === (body as any).objectId) continue;
        const dist = Math.hypot(src.position.x - canvasX, src.position.y - canvasY);
        if (dist < minDist) {
          minDist = dist;
          parentSource = src;
        }
      }
    }

    if (parentSource) {
      const parentBody = rt.sync.getPairs().get(parentSource.id)?.body || store.getObject(parentSource.id)?.body;
      if (parentBody) {
        customData.parentGravitySource = parentSource.id;
        console.log(`[Celestial Drag Stabilizer] Parent detected: ${parentSource.id} for dragged body: ${(body as any).objectId}`);

        const parentRadius = parentBody.circleRadius || (parentBody as any).customData?.celestialConfig?.radius || 35;
        const childRadius = body.circleRadius || config.radius || 14;
        const minSafeRadius = parentRadius + childRadius + 30;

        let currentRadius = minDist;
        if (currentRadius < minSafeRadius) {
          currentRadius = minSafeRadius;
        }

        const angle = Math.atan2(canvasY - parentBody.position.y, canvasX - parentBody.position.x);
        const G = radialGravity.getConfig().gravitationalConstant;
        const softening = radialGravity.getConfig().softeningFactor ?? 100;

        const { OrbitSpawner } = await import('../orbits/orbitSpawner');

        OrbitSpawner.spawnCircularOrbit({
          centerBody: parentBody,
          orbitingBody: body,
          radius: currentRadius,
          angle: angle,
          clockwise: config.orbitalDefaults?.preferredDirection !== 'counterclockwise',
          initialVelocityMultiplier: config.orbitalDefaults?.initialVelocityMultiplier ?? 1.0,
        }, G, softening);

        console.log(`[Celestial Drag Stabilizer] Orbit re-stabilized around ${parentSource.id} at radius ${currentRadius.toFixed(1)}`);
      }
    }
  }, []);

  const stabilizeDraggedCelestialRef = useRef<((body: Body) => void) | null>(null);
  stabilizeDraggedCelestialRef.current = stabilizeDraggedCelestial;

  // ── Mount ──────────────────────────────────────────────────────────────────

  useEffect(() => {
    const el = mountRef.current;
    if (!el) return;

    let alive = true;
    let canvasEl: HTMLCanvasElement | null = null;
    let lastSelectTime = 0;

    let handleMouseDown: ((e: MouseEvent) => void) | null = null;
    let handleMouseMove: ((e: MouseEvent) => void) | null = null;
    let handleMouseUp: ((e: MouseEvent) => void) | null = null;
    let handleDoubleClick: ((e: MouseEvent) => void) | null = null;
    let handleContextMenu: ((e: MouseEvent) => void) | null = null;
    let handleWheel: ((e: WheelEvent) => void) | null = null;

    (async () => {
      try {
        const [
          { SandboxRuntime },
          { DragController },
          { SelectionManager },
          { RuntimeControls },
          { ConstraintRegistry },
          { ConstraintRenderer },
          { GravityRenderer },
          Matter,
        ] = await Promise.all([
          import('../engine/runtime'),
          import('../interactions/drag'),
          import('../interactions/selection'),
          import('../interactions/controls'),
          import('../constraints/constraintRegistry'),
          import('../constraints/constraintRenderer'),
          import('../gravity/gravityRenderer'),
          import('matter-js'),
        ]);

        const rt = new SandboxRuntime();
        runtimeRef.current = rt;

        // Initialize centralized state management
        const store = new RuntimeStore();
        storeRef.current = store;
        store.setRuntimeState('uninitialized');

        const propertyController = new PropertyController(store, rt);
        propertyControllerRef.current = propertyController;

        // Force react update on property changes
        propertyController.subscribe('propertyChanged', () => {
          setPropertyVersion((v) => v + 1);
        });
        propertyController.subscribe('constraintUpdated', () => {
          setPropertyVersion((v) => v + 1);
        });



        // 1. Init renderer
        await rt.init(el);
        if (!alive) { rt.destroy(); return; }

        // 2. Interaction systems
        const canvas = rt.renderer.getApp().canvas as HTMLCanvasElement;
        canvasEl = canvas;
        const drag = new DragController(rt.physics.getEngine(), canvas);
        const selection = new SelectionManager();
        const controls = new RuntimeControls(rt);
        drag.enable();

        let isPanning = false;
        let startPointerX = 0;
        let startPointerY = 0;
        let startPanX = 0;
        let startPanY = 0;
        let hasDragged = false;
        let dragStartedOnCanvas = false;

        handleMouseDown = (e: MouseEvent) => {
          const isRightClick = e.button === 2;
          const isMiddleClick = e.button === 1;
          const isSpaceHeld = spacePressedRef.current;

          dragStartedOnCanvas = true;

          // Track values in case the user starts dragging empty space to pan
          hasDragged = false;
          startPointerX = e.clientX;
          startPointerY = e.clientY;
          startPanX = panXRef.current;
          startPanY = panYRef.current;

          if (isRightClick || isMiddleClick || isSpaceHeld) {
            isPanning = true;
            canvas.style.cursor = 'grabbing';
            drag.disable();
            e.preventDefault();
          } else if (e.button === 0) {
            isPanning = false; // Checked dynamically in handleMouseMove to separate empty space drag from asset drag

            const rect = canvas.getBoundingClientRect();
            const clickX = ((e.clientX - rect.left) / rect.width) * canvas.width;
            const clickY = ((e.clientY - rect.top) / rect.height) * canvas.height;

            const worldX = (clickX - panXRef.current) / zoomRef.current;
            const worldY = (clickY - panYRef.current) / zoomRef.current;

            const bodies = Matter.Composite.allBodies(rt.physics.getEngine().world);
            const clickedBodies = Matter.Query.point(bodies, { x: worldX, y: worldY });
            const targetBody = clickedBodies.find((b: any) => {
              const id = (b as any).objectId || b.label;
              return id && !id.startsWith('ground') && !id.startsWith('wall') && id !== 'boundary';
            });

            if (targetBody) {
              const bodyId = (targetBody as any).objectId || targetBody.label;
              console.log(`[Canvas Direct Click] Selected body synchronously: ${bodyId}`);
              lastSelectTime = Date.now();
              drag.enable();
              selection.select(bodyId);
            }
          }
        };

        handleMouseMove = (e: MouseEvent) => {
          // If the mouse buttons are released, reset drag origin safely
          if (e.buttons === 0) {
            dragStartedOnCanvas = false;
          }

          // If the user does a standard left-click drag and NO physics body is actively grabbed,
          // then the user is dragging empty space, and we dynamically initiate panning!
          // Crucially, this only triggers if the click drag actually started ON the canvas.
          if (!isPanning && e.buttons === 1 && !spacePressedRef.current && dragStartedOnCanvas) {
            const activeGrabbedBody = drag.getMouseConstraint()?.body;
            if (!activeGrabbedBody || activeGrabbedBody.isStatic) {
              const dx = e.clientX - startPointerX;
              const dy = e.clientY - startPointerY;
              if (Math.hypot(dx, dy) > 5) {
                isPanning = true;
                hasDragged = true;
                drag.disable(); // Prevent physics mouse constraint from clicking anything else
                canvas.style.cursor = 'grabbing';
              }
            }
          }

          if (!isPanning) return;

          const dx = e.clientX - startPointerX;
          const dy = e.clientY - startPointerY;

          if (Math.hypot(dx, dy) > 3) {
            hasDragged = true;
          }

          const nextPanX = startPanX + dx;
          const nextPanY = startPanY + dy;

          handleCameraChange(zoomRef.current, nextPanX, nextPanY);
        };

        handleMouseUp = (e: MouseEvent) => {
          dragStartedOnCanvas = false;
          if (isPanning) {
            isPanning = false;

            canvas.style.cursor = spacePressedRef.current ? 'grab' : 'default';
            drag.enable();

            // If the user clicked empty space and DID NOT drag to pan, deselect!
            if (e.button === 0 && !hasDragged) {
              if (Date.now() - lastSelectTime > 100) {
                selection.deselect();
              }
            }
          }
        };

        handleDoubleClick = (e: MouseEvent) => {
          const rect = canvas.getBoundingClientRect();
          const clickX = ((e.clientX - rect.left) / rect.width) * canvas.width;
          const clickY = ((e.clientY - rect.top) / rect.height) * canvas.height;

          const worldX = (clickX - panXRef.current) / zoomRef.current;
          const worldY = (clickY - panYRef.current) / zoomRef.current;

          const bodies = Matter.Composite.allBodies(rt.physics.getEngine().world);
          const clickedBodies = Matter.Query.point(bodies, { x: worldX, y: worldY });
          const targetBody = clickedBodies.find((b: any) => {
            const id = (b as any).objectId || b.label;
            return id && !id.startsWith('ground') && !id.startsWith('wall') && id !== 'boundary';
          });

          if (!targetBody) {
            handleCameraChange(1.0, 0, 0);
          }
        };

        handleContextMenu = (e: MouseEvent) => {
          e.preventDefault();
        };

        handleWheel = (e: WheelEvent) => {
          e.preventDefault();
          const rect = canvas.getBoundingClientRect();
          const mouseX = ((e.clientX - rect.left) / rect.width) * canvas.width;
          const mouseY = ((e.clientY - rect.top) / rect.height) * canvas.height;

          const currentZoom = zoomRef.current;
          const currentPanX = panXRef.current;
          const currentPanY = panYRef.current;

          const zoomFactor = e.deltaY < 0 ? 1.08 : 0.92;
          const nextZoom = Math.min(Math.max(currentZoom * zoomFactor, 0.25), 2.5);

          // Focus zoom to mouse position
          const worldX = (mouseX - currentPanX) / currentZoom;
          const worldY = (mouseY - currentPanY) / currentZoom;

          const nextPanX = mouseX - worldX * nextZoom;
          const nextPanY = mouseY - worldY * nextZoom;

          handleCameraChange(nextZoom, nextPanX, nextPanY);
        };

        canvas.addEventListener('mousedown', handleMouseDown);
        canvas.addEventListener('mousemove', handleMouseMove);
        canvas.addEventListener('mouseup', handleMouseUp);
        canvas.addEventListener('dblclick', handleDoubleClick);
        canvas.addEventListener('contextmenu', handleContextMenu);
        canvas.addEventListener('wheel', handleWheel, { passive: false });

        selection.onChange((obj) => {
          const prevId = storeRef.current?.getSelectedObjectId();
          setSelected(obj);
          if (obj) {
            lastSelectTime = Date.now();
            store.setSelectedObject(obj.id);
            // Automatically upgrade observables for the selected object to render Force, Velocity, and Acceleration
            observableEngineRef.current?.registerObservable({
              objectId: obj.id,
              types: ['force', 'velocity', 'acceleration'],
              label: obj.metadata?.label || obj.id,
              color: 0xffffff,
            });
          } else {
            if (prevId) {
              // Restore default observables for the previous selected object
              if (prevId === 'falling-ball') {
                observableEngineRef.current?.registerObservable({
                  objectId: 'falling-ball',
                  types: ['velocity', 'acceleration'],
                  label: 'Falling object',
                  color: 0xf87171,
                });
              } else if (prevId === 'pendulum-bob') {
                observableEngineRef.current?.registerObservable({
                  objectId: 'pendulum-bob',
                  types: ['angularVelocity', 'velocity'],
                  label: 'Pendulum',
                  color: 0x8b5cf6,
                });
              } else if (prevId === 'spring-bob') {
                observableEngineRef.current?.registerObservable({
                  objectId: 'spring-bob',
                  types: ['velocity', 'kineticEnergy'],
                  label: 'Spring bob',
                  color: 0x10b981,
                });
              } else if (prevId === 'collision-ball-a') {
                observableEngineRef.current?.registerObservable({
                  objectId: 'collision-ball-a',
                  types: ['momentum', 'kineticEnergy'],
                  label: 'Collision A',
                  color: 0xfacc15,
                });
              } else if (prevId === 'collision-ball-b') {
                observableEngineRef.current?.registerObservable({
                  objectId: 'collision-ball-b',
                  types: ['momentum', 'kineticEnergy'],
                  label: 'Collision B',
                  color: 0x38bdf8,
                });
              } else if (!prevId.startsWith('ground') && !prevId.startsWith('wall')) {
                // If it's a generic spawned shape, unregister
                observableEngineRef.current?.unregisterObservable(prevId);
              }
            }
            store.clearSelection();
          }
        });

        interactionRef.current = { drag, selection, controls };

        // Real-time telemetry updating hook during active loop running
        rt.addHook({
          id: 'ui-telemetry-sync',
          afterStep: () => {
            if (rt.getState() === 'running') {
              simTimeRef.current += 16.67;
            }
            setTelemetryTick((t) => t + 1);
          },
        });

        // Listen for end of pointer drag gestures to snap dropped bodies onto constraints
        import('matter-js').then((Matter) => {
          const mc = drag.getMouseConstraint();
          if (mc) {
            Matter.Events.on(mc, 'enddrag', (event: any) => {
              if (event.body) {
                checkConstraintSnapping(event.body);

                // If it is a celestial body, automatically stabilize its orbit around the nearest gravity source!
                const customData = (event.body as any).customData;
                if (customData?.celestialComponent && customData?.celestialConfig?.affectedByGravity) {
                  stabilizeDraggedCelestialRef.current?.(event.body);
                }
              }
            });
          }
        });

        // 3. Constraint systems
        const constraintReg = new ConstraintRegistry(rt.physics, store);
        const constraintRen = new ConstraintRenderer(rt);
        constraintRegRef.current = constraintReg;
        constraintRenRef.current = constraintRen;
        constraintRen.enable(() => constraintReg.getAll());

        // Gravity diagnostics rendering overlay
        const gravityRen = new GravityRenderer(rt);
        gravityRenRef.current = gravityRen;
        gravityRen.enable();

        const observableEngine = new ObservableEngine(rt, rt.sync, propertyController);
        observableEngine.enable();
        observableEngineRef.current = observableEngine;

        // 4. Build scene
        const dyn = await buildScene(rt, el, { drag, selection, controls }, constraintReg, store);
        if (!alive) { rt.destroy(); return; }

        dynRef.current = dyn;
        setBodyCount(dyn.length);

        observableEngineRef.current?.registerObservable({
          objectId: 'falling-ball',
          types: ['velocity', 'acceleration'],
          label: 'Falling object',
          color: 0xf87171,
        });
        observableEngineRef.current?.registerObservable({
          objectId: 'pendulum-bob',
          types: ['angularVelocity', 'velocity'],
          label: 'Pendulum',
          color: 0x8b5cf6,
        });
        observableEngineRef.current?.registerObservable({
          objectId: 'spring-bob',
          types: ['velocity', 'kineticEnergy'],
          label: 'Spring bob',
          color: 0x10b981,
        });
        observableEngineRef.current?.registerObservable({
          objectId: 'collision-ball-a',
          types: ['momentum', 'kineticEnergy'],
          label: 'Collision A',
          color: 0xfacc15,
        });
        observableEngineRef.current?.registerObservable({
          objectId: 'collision-ball-b',
          types: ['momentum', 'kineticEnergy'],
          label: 'Collision B',
          color: 0x38bdf8,
        });

        // 5. Start loop
        rt.start();
        store.setRuntimeState('running');
        setRunning(true);
        setReady(true);
      } catch (err) {
        console.error('[SandboxCanvas] init error:', err);
      }
    })();

    return () => {
      alive = false;
      if (canvasEl) {
        if (handleMouseDown) canvasEl.removeEventListener('mousedown', handleMouseDown);
        if (handleMouseMove) canvasEl.removeEventListener('mousemove', handleMouseMove);
        if (handleMouseUp) canvasEl.removeEventListener('mouseup', handleMouseUp);
        if (handleDoubleClick) canvasEl.removeEventListener('dblclick', handleDoubleClick);
        if (handleContextMenu) canvasEl.removeEventListener('contextmenu', handleContextMenu);
        if (handleWheel) canvasEl.removeEventListener('wheel', handleWheel);
      }
      interactionRef.current?.drag.destroy();
      interactionRef.current?.selection.clear();
      constraintRegRef.current?.clear();
      constraintRenRef.current?.destroy();
      gravityRenRef.current?.destroy();
      observableEngineRef.current?.destroy();
      runtimeRef.current?.destroy();
      runtimeRef.current = null;
      storeRef.current = null;
      interactionRef.current = null;
      constraintRegRef.current = null;
      constraintRenRef.current = null;
      gravityRenRef.current = null;
      observableEngineRef.current = null;
      setReady(false);
      setRunning(false);
    };
  }, []);

  // Dynamically reposition static borders (ground and walls) when the canvas container resizes
  useEffect(() => {
    const el = mountRef.current;
    if (!el || !ready) return;

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const W = entry.contentRect.width || el.clientWidth;
        const H = entry.contentRect.height || el.clientHeight;
        repositionBoundaries(W, H);
      }
    });

    resizeObserver.observe(el);

    return () => {
      resizeObserver.disconnect();
    };
  }, [ready, repositionBoundaries]);

  // Dynamically reposition static borders when state options (mode, custom size) change
  useEffect(() => {
    const el = mountRef.current;
    if (el && ready) {
      repositionBoundaries(el.clientWidth, el.clientHeight);
    }
  }, [boundaryMode, customWidth, customHeight, ready, repositionBoundaries]);

  // ── Controls ───────────────────────────────────────────────────────────────

  const togglePlay = () => {
    const ctrl = interactionRef.current?.controls;
    if (!ctrl || !ready) return;
    if (running) { ctrl.pause(); setRunning(false); }
    else { ctrl.resume(); setRunning(true); }
  };

  const spawnStar = useCallback(async (customX?: number, customY?: number) => {
    const rt = runtimeRef.current;
    const ia = interactionRef.current;
    const el = mountRef.current;
    const store = storeRef.current;
    if (!rt || !ia || !el || !store || !ready) return;

    const { createObject } = await import('../objects/objectFactory');

    const W = el.clientWidth || 800;
    const H = el.clientHeight || 600;
    const centerX = customX ?? (W / 2);
    const centerY = customY ?? (H / 2);
    const starId = 'orbit-star';

    // Remove old star if it exists to avoid duplicates
    const oldObj = store.getObject(starId);
    if (oldObj) {
      rt.physics.removeBodies(oldObj.body);
      rt.sync.unregister(starId);
      store.removeObject(starId);
      rt.gravitySystem.getRadialGravity().removeGravitySource(starId);
    }

    const starObj = createObject({
      id: starId,
      type: 'circle',
      x: centerX,
      y: centerY,
      radius: 35,
      isStatic: true, // Fixed central solar anchor
      fillColor: 0xeab308, // Glowing Golden Sun
      strokeColor: 0xf97316, // Solar Orange Outline
      strokeWidth: 3.5,
    });
    starObj.body.label = 'Orbit Star';
    (starObj.body as any).customData = { mass: 800 };

    rt.renderer.getViewport().addChild(starObj.display);
    rt.physics.addBodies(starObj.body);
    rt.sync.register(starObj.id, starObj.body, starObj.display);
    store.addObject(starObj);

    // Register as Gravity Source in RadialGravity
    rt.gravitySystem.getRadialGravity().addGravitySource({
      id: starId,
      mass: 800,
      position: { x: centerX, y: centerY },
      enabled: true,
      metadata: { isStar: true }
    });

    physicsEventBus.emit({
      type: 'OBJECT_SPAWNED',
      objectId: starId,
      metadata: { name: 'Orbit Star', shape: 'circle', mass: 800 }
    });
  }, [ready]);

  const spawnOrbitingPlanet = useCallback(async (customX?: number, customY?: number) => {
    const rt = runtimeRef.current;
    const ia = interactionRef.current;
    const el = mountRef.current;
    const store = storeRef.current;
    if (!rt || !ia || !el || !store || !ready) return;

    const { createObject } = await import('../objects/objectFactory');
    const Matter = await import('matter-js');

    // 1. Ensure Star exists. If not, spawn it first!
    let star = store.getObject('orbit-star');
    if (!star) {
      await spawnStar();
      star = store.getObject('orbit-star');
    }
    if (!star) return;

    const starPos = star.body.position;

    // 2. Spawn planet at an offset above the star or custom position
    const planetId = uid('planet');
    const radius = 11 + Math.random() * 5;

    let planetX: number;
    let planetY: number;
    let offset: number;
    let angle: number;

    if (customX !== undefined && customY !== undefined) {
      planetX = customX;
      planetY = customY;
      const dx = planetX - starPos.x;
      const dy = planetY - starPos.y;
      offset = Math.hypot(dx, dy);
      angle = Math.atan2(dy, dx);
    } else {
      offset = 120 + Math.random() * 50;
      planetX = starPos.x;
      planetY = starPos.y - offset;
      angle = -Math.PI / 2;
    }

    const { fill, stroke } = nextColour();
    const planetObj = createObject({
      id: planetId,
      type: 'circle',
      x: planetX,
      y: planetY,
      radius: radius,
      restitution: 0.1,
      friction: 0.05,
      frictionAir: 0,
      density: 0.002,
      fillColor: fill,
      strokeColor: stroke,
      strokeWidth: 2,
    });
    planetObj.body.label = 'Orbiting Planet';

    // 3. Solve and apply circular orbital velocity using our standardized OrbitSpawner module
    const G = rt.gravitySystem.getRadialGravity().getConfig().gravitationalConstant;
    const softening = rt.gravitySystem.getRadialGravity().getConfig().softeningFactor ?? 100;
    const { OrbitSpawner } = await import('../orbits/orbitSpawner');
    OrbitSpawner.spawnCircularOrbit({
      centerBody: star.body,
      orbitingBody: planetObj.body,
      radius: offset,
      angle: angle,
      clockwise: true,
    }, G, softening);

    rt.renderer.getViewport().addChild(planetObj.display);
    rt.physics.addBodies(planetObj.body);
    rt.sync.register(planetObj.id, planetObj.body, planetObj.display);
    ia.selection.register(planetObj);
    store.addObject(planetObj);
    dynRef.current.push(planetObj.body);
    setBodyCount(dynRef.current.length);

    physicsEventBus.emit({
      type: 'OBJECT_SPAWNED',
      objectId: planetId,
      metadata: { name: 'Orbit Planet', shape: 'circle', mass: planetObj.body.mass }
    });
  }, [ready, spawnStar]);

  // Synchronize React states reactively to the underlying modular GravitySystem
  useEffect(() => {
    const rt = runtimeRef.current;
    const el = mountRef.current;
    if (rt && ready && el) {
      rt.gravitySystem.setMode(gravityMode);
      rt.gravitySystem.getRadialGravity().setConfig({
        gravitationalConstant: gConstant,
        debug: radialDebug,
      });

      // Synchronize boundaries dynamically!
      repositionBoundaries(el.clientWidth, el.clientHeight);
    }
  }, [ready, gravityMode, gConstant, radialDebug, repositionBoundaries]);

  function handleModeChange(mode: 'linear' | 'radial') {
    setGravityMode(mode);
    const rt = runtimeRef.current;
    if (rt) {
      rt.gravitySystem.setMode(mode);
      if (mode === 'radial') {
        rt.gravitySystem.getRadialGravity().setConfig({
          gravitationalConstant: gConstant,
          debug: radialDebug
        });
      }
    }
  }



  const handleCameraChange = useCallback((newZoom: number, newPanX: number, newPanY: number) => {
    setZoom(newZoom);
    setPanX(newPanX);
    setPanY(newPanY);
    zoomRef.current = newZoom;
    panXRef.current = newPanX;
    panYRef.current = newPanY;

    const rt = runtimeRef.current;
    if (!rt) return;

    const vp = rt.renderer.getViewport();

    // Scale viewport
    vp.scale.set(newZoom);

    // Apply translation panning
    vp.position.set(newPanX, newPanY);

    // Synchronize boundaries dynamically!
    const el = mountRef.current;
    if (el) {
      repositionBoundaries(el.clientWidth, el.clientHeight, newZoom, newPanX, newPanY);
    }
    // Synchronize physics mouse constraint scale and offset
    const drag = interactionRef.current?.drag;
    if (drag) {
      const mouse = drag.getMouse();
      if (mouse) {
        const canvas = rt.renderer.getApp().canvas as HTMLCanvasElement;
        if (canvas) {
          const { width: cssW, height: cssH } = canvas.getBoundingClientRect();
          const baseScaleX = canvas.width / (cssW || 1);
          const baseScaleY = canvas.height / (cssH || 1);

          mouse.scale.x = baseScaleX / newZoom;
          mouse.scale.y = baseScaleY / newZoom;
          mouse.offset.x = newPanX / baseScaleX;
          mouse.offset.y = newPanY / baseScaleY;
        }
      }
    }
  }, [repositionBoundaries]);

  const handleReset = useCallback(async () => {
    const rt = runtimeRef.current;
    const ia = interactionRef.current;
    const creg = constraintRegRef.current;
    const el = mountRef.current;
    const store = storeRef.current;
    if (!rt || !ia || !creg || !el || !store || !ready) return;

    const wasRunning = running;
    rt.pause();
    store.reset();
    simTimeRef.current = 0;

    // Reset camera zoom/pan states and physics mouse
    handleCameraChange(1.0, 0, 0);

    // Clear old gravity sources during system reset
    if (rt.gravitySystem) {
      rt.gravitySystem.getRadialGravity().clear();
    }

    // Clean up textbook-example specific HTML overlays
    const burnOverlay = document.getElementById('example-burn-overlay');
    if (burnOverlay) burnOverlay.remove();
    const energyOverlay = document.getElementById('example-energy-overlay');
    if (energyOverlay) energyOverlay.remove();

    const dyn = await buildScene(rt, el, ia, creg, store);
    dynRef.current = dyn;
    setBodyCount(dyn.length);
    setSelected(null);

    // Sync boundaries
    repositionBoundaries(el.clientWidth, el.clientHeight);

    // Restore correct gravity behaviors based on active mode
    if (gravityMode === 'linear') {
      ia.controls.setGravity(gravity === 'custom' ? gravityValue : GRAVITY_VALUES[gravity]);
    }

    ia.controls.setSimulationSpeed(speed);
    if (wasRunning) {
      rt.start();
      store.setRuntimeState('running');
    }
  }, [ready, running, gravity, gravityValue, speed, gravityMode, handleCameraChange, repositionBoundaries]);

  const handleSelectExample = useCallback(async (exampleId: string) => {
    const rt = runtimeRef.current;
    const ia = interactionRef.current;
    const store = storeRef.current;
    const propCtrl = propertyControllerRef.current;
    const obsEngine = observableEngineRef.current;
    if (!rt || !ia || !store || !propCtrl || !obsEngine || !ready) return;

    // Clean up example-specific HTML overlays before loading the new one
    const burnOverlay = document.getElementById('example-burn-overlay');
    if (burnOverlay) burnOverlay.remove();
    const energyOverlay = document.getElementById('example-energy-overlay');
    if (energyOverlay) energyOverlay.remove();

    const examples = getAllExamples();
    const entry = examples.find((e: any) => e.id === exampleId);
    if (!entry) return;

    setSelectedExampleId(exampleId);
    setSelected(null);
    simTimeRef.current = 0;

    const initialZoom = entry.config.camera?.zoom ?? 1.0;
    handleCameraChange(initialZoom, 0, 0);

    // Call the generic orchestrator loader
    await loadExample(rt, store, propCtrl, obsEngine, ia.selection, entry.config);

    // Synchronize React state values from the loaded example config
    setGravityMode(entry.config.gravityMode ?? 'radial');
    if (entry.config.gConstant !== undefined) {
      setGConstant(entry.config.gConstant);
    }
    setRunning(true);

    // Update body count state dynamically
    const dynamicBodies = rt.physics.getWorld().bodies.filter(b => !b.isStatic);
    setBodyCount(dynamicBodies.length);
    dynRef.current = dynamicBodies;
  }, [ready, handleCameraChange]);

  const spawnShape = useCallback(async (type: 'circle' | 'rectangle') => {
    const rt = runtimeRef.current;
    const ia = interactionRef.current;
    const el = mountRef.current;
    const store = storeRef.current;
    if (!rt || !ia || !el || !store || !ready) return;

    const { createObject } = await import('../objects/objectFactory');

    const W = el.clientWidth || 800;
    const x = 120 + Math.random() * (W - 240);
    const y = 40 + Math.random() * 50;
    const rest = 0.5 + Math.random() * 0.45;
    const size = 28 + Math.random() * 32;
    const { fill, stroke } = nextColour();
    const base = {
      x, y, restitution: rest, friction: 0.1, density: 0.002,
      fillColor: fill, strokeColor: stroke, strokeWidth: 2.5
    };

    const obj = type === 'circle'
      ? createObject({ id: uid('circle'), type: 'circle', radius: size / 2, ...base })
      : createObject({
        id: uid('rect'), type: 'rectangle', width: size, height: size,
        cornerRadius: 8, angle: Math.random() * Math.PI, ...base
      });

    rt.renderer.getViewport().addChild(obj.display);
    rt.physics.addBodies(obj.body);
    rt.sync.register(obj.id, obj.body, obj.display);
    ia.selection.register(obj);
    store.addObject(obj);
    dynRef.current.push(obj.body);
    setBodyCount(dynRef.current.length);

    // Emit spawn event so explanation card shows free-fall context
    physicsEventBus.emit({
      type: 'OBJECT_SPAWNED',
      objectId: obj.id,
      metadata: {
        shape: type,
        name: type === 'circle' ? 'Circle' : 'Rectangle',
        mass: obj.body.mass,
        gravity: gravity === 'custom' ? gravityValue : GRAVITY_VALUES[gravity],
      },
    });
  }, [ready, gravity, gravityValue]);

  const blast = useCallback(async () => {
    if (!ready) return;
    const Matter = await import('matter-js');
    dynRef.current.forEach((b) => {
      Matter.Body.applyForce(b, b.position, { x: 0, y: -0.055 * b.mass });
      Matter.Body.setAngularVelocity(b, b.angularVelocity + (Math.random() - 0.5) * 0.3);
    });
  }, [ready]);

  const push = useCallback(async (dir: 'left' | 'right') => {
    if (!ready) return;
    const Matter = await import('matter-js');
    const fx = (dir === 'left' ? -1 : 1) * 0.028;
    dynRef.current.forEach((b) => Matter.Body.applyForce(b, b.position, { x: fx * b.mass, y: 0 }));
  }, [ready]);

  function changeGravity(preset: Exclude<GravityPreset, 'custom'>) {
    setGravity(preset);
    const val = GRAVITY_VALUES[preset];
    setGravityValue(val);
    propertyControllerRef.current?.updateGlobalGravity(val);
  }

  function handleGravitySliderChange(val: number) {
    setGravityValue(val);
    const matchedPreset = (Object.keys(GRAVITY_VALUES) as Exclude<GravityPreset, 'custom'>[]).find(
      (key) => Math.abs(GRAVITY_VALUES[key] - val) < 0.01
    );
    if (matchedPreset) {
      setGravity(matchedPreset);
    } else {
      setGravity('custom');
    }
    propertyControllerRef.current?.updateGlobalGravity(val);
  }

  const changeSpeed = (val: number) => {
    setSpeed(val);
    interactionRef.current?.controls.setSimulationSpeed(val);
  };



  // ── Panel drag-and-drop ────────────────────────────────────────────────────

  // Connect constraint to existing body, or spawn new complete system
  const spawnConstraintAt = useCallback(async (
    type: 'pivot' | 'spring' | 'rope',
    canvasX: number,
    canvasY: number,
    hoveredBody: Body | null,
  ) => {
    const rt = runtimeRef.current;
    const ia = interactionRef.current;
    const creg = constraintRegRef.current;
    const store = storeRef.current;
    if (!rt || !ia || !creg || !store || !ready) return;

    const { createObject } = await import('../objects/objectFactory');
    const { createConstraint } = await import('../constraints/constraintFactory');
    const Matter = await import('matter-js');
    const vp = rt.renderer.getViewport();

    const constraintId = uid('constraint');

    if (type === 'pivot') {
      if (hoveredBody) {
        const dist = Math.hypot(hoveredBody.position.x - canvasX, hoveredBody.position.y - canvasY);
        creg.add(createConstraint({
          id: constraintId,
          type: 'pivot',
          body: hoveredBody,
          anchor: { x: canvasX, y: canvasY },
          length: dist > 10 ? dist : 100,
          stiffness: 1,
          damping: 0.002,
        }));
      } else {
        // Spawn standalone ceiling anchor peg
        const pin = createObject({
          id: uid('pivot-pin'), type: 'circle',
          x: canvasX, y: canvasY, radius: 6,
          isStatic: true, fillColor: 0x334155, strokeColor: 0x475569, strokeWidth: 1,
        });
        vp.addChild(pin.display);
        rt.physics.addBodies(pin.body);
        rt.sync.register(pin.id, pin.body, pin.display);

        // Spawn a lightweight swinging receptor sensor
        const sensor = Matter.Bodies.circle(canvasX, canvasY + 120, 6, {
          isSensor: true,
          label: `sensor-target:${constraintId}`,
          density: 0.001,
          frictionAir: 0.05,
        });
        rt.physics.addBodies(sensor);

        creg.add(createConstraint({
          id: constraintId,
          type: 'pivot',
          body: sensor,
          anchor: { x: canvasX, y: canvasY },
          length: 120,
          stiffness: 1,
          damping: 0.002,
        }));
      }
    } else if (type === 'spring') {
      if (hoveredBody) {
        const anchorX = hoveredBody.position.x;
        const anchorY = Math.max(20, hoveredBody.position.y - 120);

        const ceiling = createObject({
          id: uid('spring-anchor'), type: 'rectangle',
          x: anchorX, y: anchorY, width: 30, height: 10,
          isStatic: true, fillColor: 0x1e293b, strokeColor: 0x334155, strokeWidth: 1,
        });
        vp.addChild(ceiling.display);
        rt.physics.addBodies(ceiling.body);
        rt.sync.register(ceiling.id, ceiling.body, ceiling.display);

        creg.add(createConstraint({
          id: constraintId,
          type: 'spring',
          bodyA: ceiling.body, bodyB: hoveredBody,
          length: 100, stiffness: 0.02, damping: 0.01,
        }));
      } else {
        // Spawn standalone spring hanger ceiling block
        const ceiling = createObject({
          id: uid('spring-anchor'), type: 'rectangle',
          x: canvasX, y: canvasY, width: 30, height: 10,
          isStatic: true, fillColor: 0x1e293b, strokeColor: 0x334155, strokeWidth: 1,
        });
        vp.addChild(ceiling.display);
        rt.physics.addBodies(ceiling.body);
        rt.sync.register(ceiling.id, ceiling.body, ceiling.display);

        // Spawn a lightweight bouncing receptor sensor
        const sensor = Matter.Bodies.circle(canvasX, canvasY + 100, 6, {
          isSensor: true,
          label: `sensor-target:${constraintId}`,
          density: 0.001,
          frictionAir: 0.05,
        });
        rt.physics.addBodies(sensor);

        creg.add(createConstraint({
          id: constraintId,
          type: 'spring',
          bodyA: ceiling.body, bodyB: sensor,
          length: 100, stiffness: 0.02, damping: 0.01,
        }));
      }
    } else if (type === 'rope') {
      if (hoveredBody) {
        const anchorX = hoveredBody.position.x;
        const anchorY = Math.max(20, hoveredBody.position.y - 100);

        const anchor = createObject({
          id: uid('rope-anchor'), type: 'circle',
          x: anchorX, y: anchorY, radius: 5,
          isStatic: true, fillColor: 0x334155, strokeColor: 0x475569, strokeWidth: 1,
        });
        vp.addChild(anchor.display);
        rt.physics.addBodies(anchor.body);
        rt.sync.register(anchor.id, anchor.body, anchor.display);

        creg.add(createConstraint({
          id: constraintId,
          type: 'rope',
          bodyA: anchor.body, bodyB: hoveredBody,
          length: Math.abs(hoveredBody.position.y - anchorY), stiffness: 0.9,
        }));
      } else {
        // Spawn standalone rope hanger
        const anchor = createObject({
          id: uid('rope-anchor'), type: 'circle',
          x: canvasX, y: canvasY, radius: 5,
          isStatic: true, fillColor: 0x334155, strokeColor: 0x475569, strokeWidth: 1,
        });
        vp.addChild(anchor.display);
        rt.physics.addBodies(anchor.body);
        rt.sync.register(anchor.id, anchor.body, anchor.display);

        let prevBody = anchor.body;
        const ropeSegL = 50;

        // Spawn first two physical links
        for (let i = 0; i < 2; i++) {
          const { fill, stroke } = nextColour();
          const link = createObject({
            id: uid('rope-link'), type: 'circle',
            x: canvasX, y: canvasY + ropeSegL * (i + 1),
            radius: 12, restitution: 0.3, friction: 0.1, density: 0.003,
            fillColor: fill, strokeColor: stroke, strokeWidth: 2.5,
          });
          vp.addChild(link.display);
          rt.physics.addBodies(link.body);
          rt.sync.register(link.id, link.body, link.display);
          ia.selection.register(link);
          store.addObject(link);
          dynRef.current.push(link.body);
          setBodyCount(dynRef.current.length);

          creg.add(createConstraint({
            type: 'rope',
            bodyA: prevBody, bodyB: link.body,
            length: ropeSegL, stiffness: 0.9,
          }));
          prevBody = link.body;
        }

        // The third (terminal) link is the receptor sensor bob
        const sensor = Matter.Bodies.circle(canvasX, canvasY + ropeSegL * 3, 6, {
          isSensor: true,
          label: `sensor-target:${constraintId}`,
          density: 0.001,
          frictionAir: 0.05,
        });
        rt.physics.addBodies(sensor);

        creg.add(createConstraint({
          id: constraintId,
          type: 'rope',
          bodyA: prevBody, bodyB: sensor,
          length: ropeSegL, stiffness: 0.9,
        }));
      }
    }
  }, [ready]);

  // Spawn a free constraint system when clicking the menu button directly
  const spawnConstraintShape = useCallback(async (type: 'pivot' | 'spring' | 'rope') => {
    const rt = runtimeRef.current;
    const ia = interactionRef.current;
    const creg = constraintRegRef.current;
    const el = mountRef.current;
    if (!rt || !ia || !creg || !el || !ready) return;

    const W = el.clientWidth || 800;
    const y = 80 + Math.random() * 40;
    const x = 120 + Math.random() * (W - 240);

    await spawnConstraintAt(type, x, y, null);
  }, [ready, spawnConstraintAt]);

  /**
   * Spawn a pendulum-rope asset at the given canvas position.
   *
   * Drops a complete, ready-to-swing pendulum arm:
   *   • A static ceiling anchor pin (the pivot)
   *   • N small rope-link circles connected by rope constraints
   *   • A glowing receptor sensor bob at the bottom that accepts any
   *     dropped circle or rectangle via checkConstraintSnapping()
   *
   * The user can then drag any Shape asset and drop it onto the
   * blinking bob to attach it as the pendulum weight.
   */
  const spawnPendulumRope = useCallback(async (
    canvasX: number,
    canvasY: number,
  ) => {
    const rt = runtimeRef.current;
    const ia = interactionRef.current;
    const creg = constraintRegRef.current;
    const store = storeRef.current;
    if (!rt || !ia || !creg || !store || !ready) return;

    const { createObject } = await import('../objects/objectFactory');
    const { createConstraint } = await import('../constraints/constraintFactory');
    const Matter = await import('matter-js');
    const vp = rt.renderer.getViewport();

    const ARM_LEN = 160; // px — pendulum arm length (pin → bob)

    // ── 1. Static ceiling anchor pin ──────────────────────────────────────
    const pin = createObject({
      id: uid('rope-pin'), type: 'circle',
      x: canvasX, y: canvasY, radius: 7,
      isStatic: true,
      fillColor: 0x1e293b, strokeColor: 0x6366f1, strokeWidth: 2.5,
    });
    vp.addChild(pin.display);
    rt.physics.addBodies(pin.body);
    rt.sync.register(pin.id, pin.body, pin.display);

    // ── 2. Terminal receptor sensor with visible drop-zone display ──────────
    const terminalId = uid('rope-terminal');
    const sensorDispId = uid('rope-sensor-disp');

    const sensor = Matter.Bodies.circle(
      canvasX,
      canvasY + ARM_LEN,
      16,
      {
        isSensor: true,
        // Encode both IDs so checkConstraintSnapping can clean up the display
        label: `sensor-target:${terminalId}:${sensorDispId}`,
        density: 0.0005,
        frictionAir: 0.04,
      },
    );
    rt.physics.addBodies(sensor);

    creg.add(createConstraint({
      id: terminalId,
      type: 'rope',
      bodyA: pin.body,
      bodyB: sensor,
      length: ARM_LEN,
      stiffness: 1,
    }));

    // ── 4. Visible drop-zone ring that tracks the sensor via SyncRegistry ───
    const PIXI = await import('pixi.js');
    const dropZone = new PIXI.Container();

    const ring = new PIXI.Graphics();
    // Outer glow rings
    ring.lineStyle(2.5, 0x6366f1, 0.9);
    ring.drawCircle(0, 0, 20);
    ring.lineStyle(1.5, 0x818cf8, 0.35);
    ring.drawCircle(0, 0, 32);
    // Inner filled dot
    ring.beginFill(0x4f46e5, 0.35);
    ring.drawCircle(0, 0, 10);
    ring.endFill();
    // Crosshair guides
    ring.lineStyle(1, 0x818cf8, 0.6);
    ring.moveTo(-16, 0); ring.lineTo(16, 0);
    ring.moveTo(0, -16); ring.lineTo(0, 16);

    dropZone.addChild(ring);
    dropZone.x = canvasX;
    dropZone.y = canvasY + ARM_LEN;
    vp.addChild(dropZone);

    // Register so the sync loop keeps the ring over the dangling sensor each frame
    rt.sync.register(sensorDispId, sensor, dropZone);

    // Track the pin so bodyCount reflects the new system
    dynRef.current.push(pin.body);
    setBodyCount(dynRef.current.length);
  }, [ready]);


  // Spawn at a specific canvas-relative position (used by drop handler)
  const spawnAt = useCallback(async (
    type: 'circle' | 'rectangle',
    canvasX: number,
    canvasY: number,
  ) => {
    const rt = runtimeRef.current;
    const ia = interactionRef.current;
    const store = storeRef.current;
    if (!rt || !ia || !store || !ready) return;

    const { createObject } = await import('../objects/objectFactory');
    const size = 32 + Math.random() * 24;
    const { fill, stroke } = nextColour();
    const base = {
      x: canvasX, y: canvasY, restitution: 0.6, friction: 0.1,
      density: 0.002, fillColor: fill, strokeColor: stroke, strokeWidth: 2.5
    };

    const obj = type === 'circle'
      ? createObject({ id: uid('circle'), type: 'circle', radius: size / 2, ...base })
      : createObject({
        id: uid('rect'), type: 'rectangle', width: size, height: size,
        cornerRadius: 8, ...base
      });

    rt.renderer.getViewport().addChild(obj.display);
    rt.physics.addBodies(obj.body);
    rt.sync.register(obj.id, obj.body, obj.display);
    ia.selection.register(obj);
    store.addObject(obj);
    dynRef.current.push(obj.body);
    setBodyCount(dynRef.current.length);
    checkConstraintSnapping(obj.body);
  }, [ready, checkConstraintSnapping]);

  const initializeCelestialEntity = useCallback(async (
    obj: any,
    asset: import('../../config/assetsRegistry').AssetDefinition,
    canvasX: number,
    canvasY: number,
  ) => {
    const rt = runtimeRef.current;
    const store = storeRef.current;
    if (!rt || !store || !asset.celestialConfig) return;

    const config = asset.celestialConfig;
    const isStar = config.type === 'star';
    const isPlanet = config.type === 'planet';
    const isMoon = config.type === 'moon';
    const isSatellite = config.type === 'satellite';
    const isAsteroid = config.type === 'asteroid';

    const virtualMass = config.mass ?? obj.body.mass;
    const customData = {
      mass: virtualMass,
      celestialConfig: config,
      celestialComponent: true,
      orbitalComponent: true,
      gravityComponent: true,
      observableMetadata: { label: asset.name },
      runtimeCategory: config.type,
      parentGravitySource: null as string | null,
    };
    obj.body.customData = customData;
    obj.body.label = asset.name;
    // Ensure all celestial bodies have exactly 0 air friction (no atmosphere in space)
    obj.body.frictionAir = 0;
    obj.metadata = {
      ...obj.metadata,
      ...customData,
      educationalTags: ['celestial', 'orbital', config.type],
    };

    console.log(`[Celestial Initializer] Spawning ${asset.name} (${config.type}) at (x: ${canvasX.toFixed(1)}, y: ${canvasY.toFixed(1)})`);

    // Register gravity source
    if (config.isGravitySource) {
      console.log(`[Celestial Initializer] Gravity source registered: ${asset.name} with mass ${virtualMass}`);
      rt.gravitySystem.getRadialGravity().addGravitySource({
        id: obj.id,
        mass: virtualMass,
        position: { x: canvasX, y: canvasY },
        influenceRadius: config.influenceRadius ?? (config.radius ? config.radius * 20 : 1000),
        enabled: true,
        metadata: {
          isStar,
          isPlanet,
          isMoon,
          gravityStrength: config.gravityStrength ?? 1.0,
        }
      });
    }

    // Register gravity body
    if (config.affectedByGravity) {
      console.log(`[Celestial Initializer] Gravity body registered: ${asset.name} with mass ${virtualMass}`);
      rt.gravitySystem.getRadialGravity().addGravityBody({
        id: obj.id,
        body: obj.body,
        mass: virtualMass,
        affectedByGravity: true,
        ignoreGravity: false,
      });
    }

    // Register Observables
    if (config.affectedByGravity) {
      console.log(`[Celestial Initializer] Observables telemetry HUD registered for: ${asset.name}`);
      observableEngineRef.current?.registerObservable({
        objectId: obj.id,
        types: ['velocity', 'acceleration', 'force'],
        label: asset.name,
        color: isPlanet ? 0x38bdf8 : isMoon ? 0xa5b4fc : 0x34d399,
      });
    }

    // Orbit Initialization
    if (config.affectedByGravity && config.orbitalDefaults?.autoOrbit !== false) {
      const radialGravity = rt.gravitySystem.getRadialGravity();
      const activeSources = radialGravity.getSources();

      let parentSource = null;
      let minDist = Infinity;

      for (const src of activeSources) {
        if (src.id === obj.id) continue;
        const dist = Math.hypot(src.position.x - canvasX, src.position.y - canvasY);
        // Find nearest heavier source to establish clean hierarchy
        if (src.mass > virtualMass && dist < minDist) {
          minDist = dist;
          parentSource = src;
        }
      }

      // Fallback: nearest active source
      if (!parentSource) {
        for (const src of activeSources) {
          if (src.id === obj.id) continue;
          const dist = Math.hypot(src.position.x - canvasX, src.position.y - canvasY);
          if (dist < minDist) {
            minDist = dist;
            parentSource = src;
          }
        }
      }

      if (parentSource) {
        const parentBody = rt.sync.getPairs().get(parentSource.id)?.body || store.getObject(parentSource.id)?.body;
        if (parentBody) {
          customData.parentGravitySource = parentSource.id;
          console.log(`[Celestial Initializer] Parent detected: ${parentSource.id} for child: ${obj.id}`);

          const parentRadius = parentBody.circleRadius || (parentBody as any).customData?.celestialConfig?.radius || 35;
          const childRadius = obj.body.circleRadius || config.radius || 14;
          const minSafeRadius = parentRadius + childRadius + 30;

          let currentRadius = minDist;
          if (currentRadius < minSafeRadius) {
            currentRadius = minSafeRadius;
          }

          const angle = Math.atan2(canvasY - parentBody.position.y, canvasX - parentBody.position.x);
          const G = radialGravity.getConfig().gravitationalConstant;
          const softening = radialGravity.getConfig().softeningFactor ?? 100;

          const { OrbitSpawner } = await import('../orbits/orbitSpawner');

          OrbitSpawner.spawnCircularOrbit({
            centerBody: parentBody,
            orbitingBody: obj.body,
            radius: currentRadius,
            angle: angle,
            clockwise: config.orbitalDefaults?.preferredDirection !== 'counterclockwise',
            initialVelocityMultiplier: config.orbitalDefaults?.initialVelocityMultiplier ?? 1.0,
          }, G, softening);

          console.log(`[Celestial Initializer] Orbit stable initialized around ${parentSource.id} at radius ${currentRadius.toFixed(1)}`);
        }
      } else {
        console.log(`[Celestial Initializer] No compatible gravity source found for ${obj.id}. Spawning in free-fall.`);
      }
    }
  }, []);

  // ── Asset Library drop handler ─────────────────────────────────────────────
  // Called by FloatingAssetPanel when user drops an asset onto the simulation canvas.
  // Translates AssetDefinition → RuntimeObject using existing objectFactory, keeping
  // all physics engine logic 100% unchanged.
  const handleAssetDrop = useCallback(async (
    asset: import('../../config/assetsRegistry').AssetDefinition,
    canvasX: number,
    canvasY: number,
  ) => {
    const rt = runtimeRef.current;
    const ia = interactionRef.current;
    const store = storeRef.current;
    if (!rt || !ia || !store || !ready) return;

    const { createObject } = await import('../objects/objectFactory');
    const { spawnType, spawnConfig } = asset;
    const isCelestial = !!asset.celestialConfig;

    const base: any = {
      x: canvasX,
      y: canvasY,
      restitution: spawnConfig.restitution ?? 0.5,
      friction: spawnConfig.friction ?? 0.3,
      density: spawnConfig.density ?? 0.002,
      fillColor: spawnConfig.fillColor,
      strokeColor: spawnConfig.strokeColor,
      strokeWidth: 2,
      isStatic: spawnConfig.isStatic ?? false,
      texture: asset.texture,
    };

    if (isCelestial) {
      base.frictionAir = 0; // Space has no atmosphere; celestial bodies must orbit without drag!
      if (asset.celestialConfig?.type === 'star') {
        base.isStatic = true;
      }
    }

    let obj;
    if (spawnType === 'circle') {
      obj = createObject({
        id: uid(`asset-${asset.id}`),
        type: 'circle',
        radius: spawnConfig.radius ?? 20,
        ...base,
      });
    } else {
      obj = createObject({
        id: uid(`asset-${asset.id}`),
        type: 'rectangle',
        width: spawnConfig.width ?? 40,
        height: spawnConfig.height ?? 40,
        cornerRadius: spawnConfig.cornerRadius ?? 6,
        ...base,
      });
    }

    rt.renderer.getViewport().addChild(obj.display);
    rt.physics.addBodies(obj.body);
    rt.sync.register(obj.id, obj.body, obj.display);

    if (isCelestial) {
      const Matter = await import('matter-js');
      if (asset.celestialConfig?.type === 'star') {
        Matter.Body.setStatic(obj.body, true);
      }
      await initializeCelestialEntity(obj, asset, canvasX, canvasY);
    }

    // Register with selection and store
    ia.selection.register(obj);
    store.addObject(obj);

    if (!obj.body.isStatic) {
      dynRef.current.push(obj.body);
      setBodyCount(dynRef.current.length);
      checkConstraintSnapping(obj.body);
    }

    // Select the dropped asset immediately so user can see property panel
    ia.selection.select(obj.id);

    // Emit spawn event so explanation card shows free-fall context
    physicsEventBus.emit({
      type: 'OBJECT_SPAWNED',
      objectId: obj.id,
      metadata: {
        shape: spawnType,
        name: asset.name,
        mass: obj.body.mass,
        gravity: gravityMode === 'radial' ? 'radial' : (gravity === 'custom' ? gravityValue : GRAVITY_VALUES[gravity]),
      },
    });
  }, [ready, checkConstraintSnapping, gravity, gravityValue, gravityMode, initializeCelestialEntity]);

  // ── Canvas HTML5 drag-and-drop bridge (for FloatingAssetPanel) ────────────
  // Uses native window-level listeners to bypass react-rnd / framer-motion event capture.
  const [assetDragOver, setAssetDragOver] = useState(false);
  const canvasWrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleDragOver = (e: DragEvent) => {
      if (!e.dataTransfer?.types.includes('application/edusim-asset')) return;
      const wrap = canvasWrapRef.current;
      if (!wrap) return;
      const r = wrap.getBoundingClientRect();
      const inside = e.clientX >= r.left && e.clientX <= r.right && e.clientY >= r.top && e.clientY <= r.bottom;
      if (inside) {
        e.preventDefault();
        if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy';
        setAssetDragOver(true);
      } else {
        setAssetDragOver(false);
      }
    };

    const handleDragEnd = () => setAssetDragOver(false);

    const handleDrop = (e: DragEvent) => {
      const wrap = canvasWrapRef.current;
      if (!wrap) return;
      const r = wrap.getBoundingClientRect();
      const inside = e.clientX >= r.left && e.clientX <= r.right && e.clientY >= r.top && e.clientY <= r.bottom;
      if (!inside) return;
      const raw = e.dataTransfer?.getData('application/edusim-asset');
      if (!raw) return;
      e.preventDefault();
      setAssetDragOver(false);
      const asset = JSON.parse(raw) as import('../../config/assetsRegistry').AssetDefinition;
      const cssX = e.clientX - r.left;
      const cssY = e.clientY - r.top;
      const worldX = (cssX - panXRef.current) / zoomRef.current;
      const worldY = (cssY - panYRef.current) / zoomRef.current;
      handleAssetDrop(asset, worldX, worldY);
    };

    window.addEventListener('dragover', handleDragOver);
    window.addEventListener('dragend', handleDragEnd);
    window.addEventListener('drop', handleDrop);
    return () => {
      window.removeEventListener('dragover', handleDragOver);
      window.removeEventListener('dragend', handleDragEnd);
      window.removeEventListener('drop', handleDrop);
    };
  }, [handleAssetDrop]);

  const onPanelPointerDown = (type: PanelDragType) =>
    (e: React.PointerEvent) => {
      if (!ready) return;

      // Pause physics engine drag controller during menu drag-and-drop to prevent automatic sticking
      interactionRef.current?.drag.disable();

      panelDragRef.current = type;
      didDragRef.current = false;   // reset flag on every fresh press
      setIsDragging(true);
      setGhostPos({ x: e.clientX, y: e.clientY });
    };

  useEffect(() => {
    if (!isDragging) return;

    const handlePointerMove = (e: PointerEvent) => {
      didDragRef.current = true;    // pointer moved — this is a drag, not a tap
      setGhostPos({ x: e.clientX, y: e.clientY });

      const canvas = mountRef.current;
      if (canvas) {
        const r = canvas.getBoundingClientRect();
        const over = (
          e.clientX >= r.left && e.clientX <= r.right &&
          e.clientY >= r.top && e.clientY <= r.bottom
        );
        setIsOverCanvas(over);

        // Query body under cursor for constraints
        const dragType = panelDragRef.current;
        if (over && dragType && ['pivot', 'spring', 'rope'].includes(dragType)) {
          const cssX = e.clientX - r.left;
          const cssY = e.clientY - r.top;
          const worldX = (cssX - panXRef.current) / zoomRef.current;
          const worldY = (cssY - panYRef.current) / zoomRef.current;
          const queryPoint = { x: worldX, y: worldY };
          const bodies = dynRef.current;

          import('matter-js').then((Matter) => {
            const hovered = bodies.find(b => Matter.Vertices.contains(b.vertices, queryPoint));
            if (hovered) {
              hoveredBodyRef.current = hovered;
              setHoveredBodyId(hovered.label || hovered.id.toString());
            } else {
              hoveredBodyRef.current = null;
              setHoveredBodyId(null);
            }
          });
        } else {
          hoveredBodyRef.current = null;
          setHoveredBodyId(null);
        }
      }
    };

    const handlePointerUp = (e: PointerEvent) => {
      const type = panelDragRef.current;
      panelDragRef.current = null;
      setIsDragging(false);
      setIsOverCanvas(false);

      // Re-enable the physics engine drag controller now that panel drag is complete
      interactionRef.current?.drag.enable();

      const hoveredBody = hoveredBodyRef.current;
      hoveredBodyRef.current = null;
      setHoveredBodyId(null);

      if (!type) return;
      const canvas = mountRef.current;
      if (!canvas) return;
      const r = canvas.getBoundingClientRect();
      // Only drop if released over the canvas
      if (e.clientX >= r.left && e.clientX <= r.right &&
        e.clientY >= r.top && e.clientY <= r.bottom) {
        const cssX = e.clientX - r.left;
        const cssY = e.clientY - r.top;
        const worldX = (cssX - panXRef.current) / zoomRef.current;
        const worldY = (cssY - panYRef.current) / zoomRef.current;
        if (['pivot', 'spring', 'rope'].includes(type)) {
          spawnConstraintAt(type as 'pivot' | 'spring' | 'rope', worldX, worldY, hoveredBody);
        } else if (type === 'pendulum-rope') {
          spawnPendulumRope(worldX, worldY);
        } else if (type === 'sun') {
          spawnStar(worldX, worldY);
        } else if (type === 'planet') {
          spawnOrbitingPlanet(worldX, worldY);
        } else {
          spawnAt(type as 'circle' | 'rectangle', worldX, worldY);
        }
      }
    };

    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', handlePointerUp);
    return () => {
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerup', handlePointerUp);
    };
  }, [isDragging, ready, spawnConstraintAt, spawnPendulumRope, spawnAt]);

  // Wheel and panning controls are handled in the main initialization useEffect

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div style={S.root}>
      {/* ── Left panel ─────────────────────────────────────── */}
      <aside
        style={{
          ...S.panel,
          position: isMobile ? 'absolute' : 'relative',
          left: 0,
          top: 0,
          zIndex: isMobile ? 300 : 'auto',
          width: leftPanelOpen ? 288 : 0,
          minWidth: leftPanelOpen ? 268 : 0,
          padding: leftPanelOpen ? '20px 16px' : 0,
          borderRight: leftPanelOpen ? S.panel.borderRight : 'none',
          opacity: leftPanelOpen ? 1 : 0,
          transition: 'all 0.35s cubic-bezier(0.4, 0, 0.2, 1)',
          overflowY: leftPanelOpen ? (activeLeftTab === 'toolbox' ? 'auto' : 'hidden') : 'hidden',
          overflowX: 'hidden',
        }}
      >
        <div style={S.header}>
          <span style={S.pulse} />
          <span style={S.tag}>Interactive Physics</span>
        </div>
        <h1 style={S.title}>EduSim Sandbox</h1>
        <p style={S.subtitle}>Drag · Select · Control</p>

        {/* Premium Tab Toggles */}
        <div style={{
          display: 'flex',
          background: 'rgba(0, 0, 0, 0.4)',
          borderRadius: '10px',
          padding: '3px',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          marginBottom: '14px',
          flexShrink: 0,
        }}>
          <button
            onClick={() => setActiveLeftTab('toolbox')}
            style={{
              flex: 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              padding: '8px 0',
              borderRadius: '8px',
              border: 'none',
              background: activeLeftTab === 'toolbox' ? 'linear-gradient(135deg, #4f46e5, #6366f1)' : 'transparent',
              color: activeLeftTab === 'toolbox' ? '#fff' : '#64748b',
              fontSize: '11px',
              fontWeight: 700,
              cursor: 'pointer',
              transition: 'all 0.25s ease',
              boxShadow: activeLeftTab === 'toolbox' ? '0 4px 12px rgba(79, 70, 229, 0.3)' : 'none',
              outline: 'none',
            }}
          >
            <Settings size={12} />
            Sandbox Toolbox
          </button>
          <button
            onClick={() => setActiveLeftTab('examples')}
            style={{
              flex: 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              padding: '8px 0',
              borderRadius: '8px',
              border: 'none',
              background: activeLeftTab === 'examples' ? 'linear-gradient(135deg, #4f46e5, #6366f1)' : 'transparent',
              color: activeLeftTab === 'examples' ? '#fff' : '#64748b',
              fontSize: '11px',
              fontWeight: 700,
              cursor: 'pointer',
              transition: 'all 0.25s ease',
              boxShadow: activeLeftTab === 'examples' ? '0 4px 12px rgba(79, 70, 229, 0.3)' : 'none',
              outline: 'none',
            }}
          >
            <BookOpen size={12} />
            Textbook Examples
          </button>
        </div>

        {activeLeftTab === 'toolbox' ? (
          <>

            {/* Status */}
            <div style={S.cards}>
              <div style={S.card}>
                <div style={S.cardLbl}>Engine</div>
                <div style={S.cardVal}>
                  <span style={{ ...S.dot, background: running ? '#10b981' : '#f59e0b' }} />
                  {ready ? (running ? 'Running' : 'Paused') : 'Loading…'}
                </div>
              </div>
              <div style={S.card}>
                <div style={S.cardLbl}>Dynamic Bodies</div>
                <div style={S.cardVal}>{bodyCount}</div>
              </div>
            </div>



            <Sep label="Controls" />
            <div style={S.row}>
              <button
                id="play-pause-btn"
                style={{
                  ...S.btn,
                  ...S.btnPrimary,
                  flex: 1,
                  border: (highlightedAsset === 'play-btn') ? '2px solid rgb(34, 211, 238)' : S.btn.border,
                  boxShadow: (highlightedAsset === 'play-btn') ? '0 0 15px rgba(34, 211, 238, 0.75)' : 'none',
                  transition: 'all 0.3s ease'
                }}
                onClick={togglePlay}
                disabled={!ready}
              >
                {running ? '⏸ Pause' : '▶ Resume'}
              </button>
              <button style={{ ...S.btn, ...S.btnGhost }} onClick={handleReset} disabled={!ready} title="Reset">↺</button>
              <button
                style={{
                  ...S.btn,
                  ...S.btnGhost,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: 38,
                  height: 38,
                  padding: 0
                }}
                onClick={() => setMaximized(!isMaximized)}
                title={isMaximized ? "Exit Full Window" : "Full Window Mode"}
              >
                {isMaximized ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
              </button>
            </div>

            {/* Tutor Explanation Toggle */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginTop: 2,
              marginBottom: 6,
              padding: '7px 10px',
              borderRadius: 10,
              background: tutorEnabled
                ? 'rgba(99, 102, 241, 0.10)'
                : 'rgba(255,255,255,0.03)',
              border: tutorEnabled
                ? '1px solid rgba(99,102,241,0.30)'
                : '1px solid rgba(255,255,255,0.07)',
              transition: 'all 0.2s ease',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ fontSize: 14 }}>🤖</span>
                <span style={{ fontSize: 11, fontWeight: 600, color: tutorEnabled ? '#a5b4fc' : '#64748b', transition: 'color 0.2s' }}>
                  AI Explanation
                </span>
              </div>
              <button
                id="tutor-toggle-btn"
                onClick={() => setTutorEnabled((v) => !v)}
                style={{
                  position: 'relative',
                  width: 38,
                  height: 20,
                  borderRadius: 10,
                  border: 'none',
                  cursor: 'pointer',
                  padding: 0,
                  background: tutorEnabled
                    ? 'linear-gradient(135deg, #6366f1, #818cf8)'
                    : 'rgba(71,85,105,0.6)',
                  boxShadow: tutorEnabled
                    ? '0 0 8px rgba(99,102,241,0.5)'
                    : 'none',
                  transition: 'all 0.25s ease',
                  flexShrink: 0,
                }}
                title={tutorEnabled ? 'Disable AI explanations' : 'Enable AI explanations'}
              >
                <span style={{
                  position: 'absolute',
                  top: 3,
                  left: tutorEnabled ? 21 : 3,
                  width: 14,
                  height: 14,
                  borderRadius: '50%',
                  background: '#fff',
                  boxShadow: '0 1px 4px rgba(0,0,0,0.35)',
                  transition: 'left 0.25s ease',
                  display: 'block',
                }} />
              </button>
            </div>

            <Sep label="Spawn Shapes — click or drag" />
            <div
              style={S.row}
            >
              <button
                id="spawn-rect-btn"
                style={{
                  ...S.btn,
                  ...S.btnIndigo,
                  flex: 1,
                  cursor: ready ? 'grab' : 'not-allowed',
                  border: (highlightedAsset === 'rectangle' || highlightedAsset === 'shape-toolbox') ? '2px solid rgb(52, 211, 153)' : S.btn.border,
                  boxShadow: (highlightedAsset === 'rectangle' || highlightedAsset === 'shape-toolbox') ? '0 0 15px rgba(52, 211, 153, 0.75)' : 'none',
                  transition: 'all 0.35s ease'
                }}
                disabled={!ready}
                onClick={() => { if (didDragRef.current) { didDragRef.current = false; return; } spawnShape('rectangle'); }}
                onPointerDown={onPanelPointerDown('rectangle')}
              >▪ Rectangle</button>
              <button
                id="spawn-circle-btn"
                style={{
                  ...S.btn,
                  ...S.btnEmerald,
                  flex: 1,
                  cursor: ready ? 'grab' : 'not-allowed',
                  border: (highlightedAsset === 'circle' || highlightedAsset === 'shape-toolbox') ? '2px solid rgb(52, 211, 153)' : S.btn.border,
                  boxShadow: (highlightedAsset === 'circle' || highlightedAsset === 'shape-toolbox') ? '0 0 15px rgba(52, 211, 153, 0.75)' : 'none',
                  transition: 'all 0.35s ease'
                }}
                disabled={!ready}
                onClick={() => { if (didDragRef.current) { didDragRef.current = false; return; } spawnShape('circle'); }}
                onPointerDown={onPanelPointerDown('circle')}
              >● Circle</button>
            </div>
            {/* Rope as a first-class shape asset */}
            <div
              style={{ ...S.row, marginTop: -2 }}
            >
              <button
                id="spawn-pendulum-rope-btn"
                style={{
                  ...S.btn,
                  width: '100%',
                  cursor: ready ? 'grab' : 'not-allowed',
                  background: (highlightedAsset === 'rope' || highlightedAsset === 'constraints-toolbox') ? 'rgba(245, 158, 11, 0.2)' : 'rgba(99,102,241,0.13)',
                  color: (highlightedAsset === 'rope' || highlightedAsset === 'constraints-toolbox') ? '#fbbf24' : '#a5b4fc',
                  borderColor: (highlightedAsset === 'rope' || highlightedAsset === 'constraints-toolbox') ? '#f59e0b' : 'rgba(99,102,241,0.28)',
                  boxShadow: (highlightedAsset === 'rope' || highlightedAsset === 'constraints-toolbox') ? '0 0 15px rgba(245, 158, 11, 0.65)' : 'none',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                  transition: 'all 0.35s ease'
                }}
                disabled={!ready}
                onClick={() => {
                  if (didDragRef.current) { didDragRef.current = false; return; }
                  const el = mountRef.current;
                  if (!el) return;
                  const W = el.clientWidth || 800;
                  spawnPendulumRope(120 + Math.random() * (W - 240), 40 + Math.random() * 30);
                }}
                onPointerDown={onPanelPointerDown('pendulum-rope')}
              >
                <span style={{ fontSize: 13 }}>🪢</span>
                <span>Rope  <span style={{ fontSize: 9, opacity: 0.65 }}>— drop bob to complete pendulum</span></span>
              </button>
            </div>

            <Sep label="Spawn Constraints — click or drag" />
            <div
              style={{ ...S.row, flexWrap: 'wrap' }}
            >
              <button
                id="spawn-pivot-btn"
                style={{
                  ...S.btn,
                  ...S.btnIndigo,
                  flex: '1 1 45%',
                  cursor: ready ? 'grab' : 'not-allowed',
                  padding: '7px 4px',
                  fontSize: 11,
                  border: (highlightedAsset === 'pivot' || highlightedAsset === 'constraints-toolbox') ? '2px solid rgb(245, 158, 11)' : S.btn.border,
                  boxShadow: (highlightedAsset === 'pivot' || highlightedAsset === 'constraints-toolbox') ? '0 0 15px rgba(245, 158, 11, 0.75)' : 'none',
                  transition: 'all 0.35s ease'
                }}
                disabled={!ready}
                onClick={() => { if (didDragRef.current) { didDragRef.current = false; return; } spawnConstraintShape('pivot'); }}
                onPointerDown={onPanelPointerDown('pivot')}
              >📌 Pivot</button>
              <button
                id="spawn-spring-btn"
                style={{
                  ...S.btn,
                  ...S.btnEmerald,
                  flex: '1 1 45%',
                  cursor: ready ? 'grab' : 'not-allowed',
                  padding: '7px 4px',
                  fontSize: 11,
                  border: (highlightedAsset === 'spring' || highlightedAsset === 'constraints-toolbox') ? '2px solid rgb(245, 158, 11)' : S.btn.border,
                  boxShadow: (highlightedAsset === 'spring' || highlightedAsset === 'constraints-toolbox') ? '0 0 15px rgba(245, 158, 11, 0.75)' : 'none',
                  transition: 'all 0.35s ease'
                }}
                disabled={!ready}
                onClick={() => { if (didDragRef.current) { didDragRef.current = false; return; } spawnConstraintShape('spring'); }}
                onPointerDown={onPanelPointerDown('spring')}
              >🌀 Spring</button>
              <button
                id="spawn-rope-chain-btn"
                style={{
                  ...S.btn,
                  ...S.btnSky,
                  width: '100%',
                  cursor: ready ? 'grab' : 'not-allowed',
                  marginTop: 4,
                  border: (highlightedAsset === 'rope' || highlightedAsset === 'constraints-toolbox') ? '2px solid rgb(245, 158, 11)' : S.btn.border,
                  boxShadow: (highlightedAsset === 'rope' || highlightedAsset === 'constraints-toolbox') ? '0 0 15px rgba(245, 158, 11, 0.75)' : 'none',
                  transition: 'all 0.35s ease'
                }}
                disabled={!ready}
                onClick={() => { if (didDragRef.current) { didDragRef.current = false; return; } spawnConstraintShape('rope'); }}
                onPointerDown={onPanelPointerDown('rope')}
              >🔗 Rope Chain</button>
            </div>

            <Sep label="Impulse" />
            <button style={{ ...S.btn, ...S.btnSky, width: '100%', marginBottom: 8 }} onClick={blast} disabled={!ready}>↑ Upward Blast</button>
            <div style={S.row}>
              <button style={{ ...S.btn, ...S.btnGhost, flex: 1 }} onClick={() => push('left')} disabled={!ready}>◀ Left</button>
              <button style={{ ...S.btn, ...S.btnGhost, flex: 1 }} onClick={() => push('right')} disabled={!ready}>Right ▶</button>
            </div>

            <Sep label="Gravity System" />
            <div style={{ ...S.gravRow, gap: 4, display: 'flex', marginBottom: 8 }}>
              <button
                style={{
                  ...S.gravBtn,
                  ...(gravityMode === 'linear' ? S.gravActive : {}),
                  flex: 1
                }}
                onClick={() => handleModeChange('linear')}
                disabled={!ready}
              >
                🍎 Linear
              </button>
              <button
                style={{
                  ...S.gravBtn,
                  ...(gravityMode === 'radial' ? S.gravActive : {}),
                  flex: 1
                }}
                onClick={() => handleModeChange('radial')}
                disabled={!ready}
              >
                🌌 Orbital
              </button>
            </div>

            {gravityMode === 'linear' ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 12 }}>
                <div style={S.gravRow}>
                  {(Object.keys(GRAVITY_VALUES) as Exclude<GravityPreset, 'custom'>[]).map((k) => (
                    <button key={k}
                      style={{ ...S.gravBtn, ...(gravity === k ? S.gravActive : {}) }}
                      onClick={() => changeGravity(k)} disabled={!ready}
                    >{k}</button>
                  ))}
                </div>
                
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, padding: '4px 8px', background: 'rgba(0, 0, 0, 0.2)', borderRadius: 8 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#94a3b8' }}>
                    <span>Gravity Acceleration (g)</span>
                    <span style={{ fontFamily: 'monospace', color: '#fbbf24' }}>
                      {gravityValue.toFixed(2)}x {gravity === 'custom' ? '(Custom)' : `(${gravity.toUpperCase()})`}
                    </span>
                  </div>
                  <input
                    type="range"
                    min={0}
                    max={4.0}
                    step={0.05}
                    value={gravityValue}
                    disabled={!ready}
                    onChange={(e) => {
                      const val = parseFloat(e.target.value);
                      handleGravitySliderChange(val);
                    }}
                    style={{ cursor: ready ? 'pointer' : 'not-allowed', accentColor: '#10b981' }}
                  />
                </div>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 12, padding: '4px 8px', background: 'rgba(0, 0, 0, 0.2)', borderRadius: 8 }}>
                <div style={{ display: 'flex', gap: 6 }}>
                  <button
                    style={{ ...S.btn, ...S.btnIndigo, flex: 1, fontSize: 10, padding: '6px 2px', cursor: ready ? 'grab' : 'not-allowed' }}
                    disabled={!ready}
                    onClick={() => { if (didDragRef.current) { didDragRef.current = false; return; } spawnStar(); }}
                    onPointerDown={onPanelPointerDown('sun')}
                  >
                    ☀️ Spawn Sun
                  </button>
                  <button
                    style={{ ...S.btn, ...S.btnSky, flex: 1, fontSize: 10, padding: '6px 2px', cursor: ready ? 'grab' : 'not-allowed' }}
                    disabled={!ready}
                    onClick={() => { if (didDragRef.current) { didDragRef.current = false; return; } spawnOrbitingPlanet(); }}
                    onPointerDown={onPanelPointerDown('planet')}
                  >
                    🌎 Spawn Orbit Planet
                  </button>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#94a3b8' }}>
                    <span>Gravitational Pull (G)</span>
                    <span style={{ fontFamily: 'monospace', color: '#fbbf24' }}>{gConstant.toFixed(4)}</span>
                  </div>
                  <input
                    type="range"
                    min={0.0003}
                    max={0.004}
                    step={0.0001}
                    value={gConstant}
                    disabled={!ready}
                    onChange={(e) => {
                      const val = parseFloat(e.target.value);
                      setGConstant(val);
                    }}
                    style={{ width: '100%', accentColor: '#38bdf8', height: 4, cursor: 'pointer' }}
                  />
                </div>

                <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', fontSize: 10, color: '#94a3b8' }}>
                  <input
                    type="checkbox"
                    checked={radialDebug}
                    disabled={!ready}
                    onChange={(e) => setRadialDebug(e.target.checked)}
                    style={{ accentColor: '#38bdf8', cursor: 'pointer' }}
                  />
                  <span>Predict Orbits & Draw Field Lines</span>
                </label>
              </div>
            )}

            <Sep label="Simulation Speed" />
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
              <input
                type="range" min={0.1} max={3} step={0.1}
                value={speed} disabled={!ready}
                onChange={(e) => changeSpeed(parseFloat(e.target.value))}
                style={{ flex: 1, accentColor: '#6366f1' }}
              />
              <span style={{ fontSize: 11, color: '#818cf8', minWidth: 30, textAlign: 'right' }}>{speed.toFixed(1)}×</span>
            </div>


            <Sep label="Constraint Tuning" />
            {storeRef.current && storeRef.current.getAllConstraints().length > 0 ? (
              <div style={S.constraintsList}>
                {storeRef.current.getAllConstraints().map((rc) => {
                  const { id, type, constraint } = rc;
                  const hasStiffness = type === 'spring' || type === 'pivot' || type === 'rope';
                  const hasDamping = type === 'spring' || type === 'pivot';
                  const hasLength = true;

                  return (
                    <div key={id} style={S.constraintCard}>
                      <div style={S.constraintCardHeader}>
                        <span style={S.constraintName}>
                          {type === 'spring' ? '🌀 Spring' : type === 'pivot' ? '📌 Pivot' : '🔗 Rope Link'}
                        </span>
                        <span style={{ fontSize: 9, color: '#475569', fontFamily: 'monospace' }}>{id}</span>
                      </div>

                      {hasStiffness && (
                        <div style={S.controlRow}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <label style={S.controlLabel}>Stiffness</label>
                            <span style={S.controlVal}>{constraint.stiffness.toFixed(3)}</span>
                          </div>
                          <div style={S.sliderContainer}>
                            <input
                              type="range"
                              min={type === 'spring' ? 0.001 : 0.05}
                              max={1.0}
                              step={type === 'spring' ? 0.002 : 0.05}
                              value={constraint.stiffness}
                              onChange={(e) => propertyControllerRef.current?.updateConstraintProperty(id, 'stiffness', parseFloat(e.target.value))}
                              style={S.slider}
                            />
                          </div>
                        </div>
                      )}

                      {hasDamping && (
                        <div style={S.controlRow}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <label style={S.controlLabel}>Damping</label>
                            <span style={S.controlVal}>{constraint.damping.toFixed(4)}</span>
                          </div>
                          <div style={S.sliderContainer}>
                            <input
                              type="range"
                              min={0.0}
                              max={0.1}
                              step={0.002}
                              value={constraint.damping}
                              onChange={(e) => propertyControllerRef.current?.updateConstraintProperty(id, 'damping', parseFloat(e.target.value))}
                              style={S.slider}
                            />
                          </div>
                        </div>
                      )}

                      {hasLength && (
                        <div style={S.controlRow}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <label style={S.controlLabel}>Rest Length</label>
                            <span style={S.controlVal}>{Math.round(constraint.length)} px</span>
                          </div>
                          <div style={S.sliderContainer}>
                            <input
                              type="range"
                              min={10}
                              max={350}
                              step={5}
                              value={constraint.length}
                              onChange={(e) => propertyControllerRef.current?.updateConstraintProperty(id, 'length', parseFloat(e.target.value))}
                              style={S.slider}
                            />
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : (
              <div style={S.noSelectionCard}>
                <span style={{ color: '#475569', fontSize: 10 }}>No active constraints to tune.</span>
              </div>
            )}

            <p style={S.hint}>
              <strong style={{ color: '#6366f1' }}>Drag</strong> objects · <strong style={{ color: '#6366f1' }}>Click</strong> to select · Use controls to shape the simulation.
            </p>

            {/* AI Query Input Section */}
            <div style={{ marginTop: 'auto', paddingTop: 20 }}>
              <div style={{
                background: 'rgba(255, 255, 255, 0.03)',
                border: '1px solid rgba(168, 85, 247, 0.2)',
                borderRadius: 12,
                padding: 12,
                boxShadow: '0 0 15px rgba(168, 85, 247, 0.1) inset'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
                  <Sparkles size={14} color="#c084fc" />
                  <span style={{ fontSize: 11, fontWeight: 700, color: '#e9d5ff', letterSpacing: '0.05em' }}>AI QUERY</span>
                </div>
                <textarea
                  value={aiPrompt}
                  onChange={e => setAiPrompt(e.target.value)}
                  onKeyDown={handleAiKeyDown}
                  disabled={aiLoading}
                  placeholder="Ask about physics..."
                  style={{
                    width: '100%',
                    background: 'rgba(0, 0, 0, 0.3)',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    borderRadius: 8,
                    padding: '8px 10px',
                    color: '#f8fafc',
                    fontSize: 12,
                    resize: 'none',
                    minHeight: 50,
                    outline: 'none',
                    opacity: aiLoading ? 0.5 : 1
                  }}
                />

                {aiLoading && (
                  <div style={{ marginTop: 8 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#c084fc', marginBottom: 4, fontWeight: 600 }}>
                      <span>Generating instructions...</span>
                      <span style={{ opacity: 0.8 }} className="animate-pulse">Please wait</span>
                    </div>
                    <div style={{ width: '100%', backgroundColor: 'rgba(255, 255, 255, 0.05)', border: '1px solid rgba(168, 85, 247, 0.1)', height: 5, borderRadius: 2.5, overflow: 'hidden', position: 'relative' }}>
                      <motion.div
                        style={{
                          height: '100%',
                          background: 'linear-gradient(90deg, #a855f7, #ec4899)',
                          borderRadius: 2.5,
                          width: '30%',
                          position: 'absolute',
                        }}
                        animate={{
                          left: ['-30%', '100%']
                        }}
                        transition={{
                          repeat: Infinity,
                          duration: 1.5,
                          ease: 'easeInOut'
                        }}
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>
          </>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', flex: 1, minHeight: 0 }}>
            {/* Search Input */}
            <div style={{ position: 'relative', width: '100%', flexShrink: 0 }}>
              <span style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: '#64748b', display: 'flex', alignItems: 'center' }}>
                <Search size={13} />
              </span>
              <input
                type="text"
                value={exampleSearch}
                onChange={e => setExampleSearch(e.target.value)}
                placeholder="Search examples..."
                style={{
                  width: '100%',
                  background: 'rgba(0, 0, 0, 0.3)',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  borderRadius: '8px',
                  padding: '8px 10px 8px 30px',
                  color: '#fff',
                  fontSize: '12px',
                  outline: 'none',
                }}
              />
            </div>

            {/* Clear Example mode button */}
            {selectedExampleId && (
              <button
                onClick={() => {
                  setSelectedExampleId(null);
                  handleReset();
                }}
                style={{
                  width: '100%',
                  padding: '8px',
                  borderRadius: '8px',
                  border: '1px dashed rgba(239, 68, 68, 0.5)',
                  background: 'rgba(239, 68, 68, 0.08)',
                  color: '#f87171',
                  fontSize: '11px',
                  fontWeight: 700,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '6px',
                  transition: 'all 0.2s',
                  flexShrink: 0,
                  outline: 'none',
                }}
              >
                <span>✕ Exit Example Mode</span>
              </button>
            )}

            {/* List of Examples */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', overflowY: 'auto', flex: 1, paddingRight: '4px' }}>
              {getAllExamples()
                .filter((ex: any) =>
                  ex.title.toLowerCase().includes(exampleSearch.toLowerCase()) ||
                  ex.description.toLowerCase().includes(exampleSearch.toLowerCase())
                )
                .map((ex: any) => {
                  const isSelected = selectedExampleId === ex.id;
                  return (
                    <div
                      key={ex.id}
                      onClick={() => handleSelectExample(ex.id)}
                      style={{
                        background: isSelected
                          ? 'linear-gradient(135deg, rgba(99, 102, 241, 0.15), rgba(79, 70, 229, 0.05))'
                          : 'rgba(255, 255, 255, 0.02)',
                        border: isSelected
                          ? '1px solid rgba(99, 102, 241, 0.45)'
                          : '1px solid rgba(255, 255, 255, 0.06)',
                        borderRadius: '12px',
                        padding: '12px',
                        cursor: 'pointer',
                        transition: 'all 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
                        boxShadow: isSelected ? '0 4px 16px rgba(99, 102, 241, 0.15)' : 'none',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '8px',
                      }}
                    >
                      <div style={{ display: 'flex', alignSelf: 'stretch', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{
                          fontSize: '8px',
                          fontWeight: 800,
                          color: '#818cf8',
                          letterSpacing: '0.08em',
                          textTransform: 'uppercase',
                        }}>{ex.category}</span>
                        {isSelected && (
                          <span style={{
                            fontSize: '9px',
                            fontWeight: 800,
                            color: '#10b981',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '3px',
                          }}>
                            ● Active
                          </span>
                        )}
                      </div>

                      <h3 style={{
                        fontSize: '13px',
                        fontWeight: 700,
                        color: isSelected ? '#a5b4fc' : '#cbd5e1',
                        margin: 0,
                      }}>{ex.title}</h3>

                      <p style={{
                        fontSize: '11px',
                        color: '#94a3b8',
                        margin: 0,
                        lineHeight: '1.4',
                      }}>{ex.description}</p>

                      {/* Launch / Play button inside the card */}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleSelectExample(ex.id);
                        }}
                        style={{
                          marginTop: '4px',
                          width: '100%',
                          padding: '8px 12px',
                          borderRadius: '6px',
                          border: 'none',
                          background: isSelected
                            ? 'linear-gradient(135deg, #10b981, #059669)'
                            : 'linear-gradient(135deg, #4f46e5, #6366f1)',
                          color: '#fff',
                          fontSize: '10.5px',
                          fontWeight: 700,
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          gap: '4px',
                          transition: 'all 0.2s',
                          boxShadow: isSelected ? '0 4px 10px rgba(16, 185, 129, 0.2)' : '0 4px 10px rgba(79, 70, 229, 0.2)',
                          outline: 'none',
                        }}
                      >
                        <Play size={10} fill="#fff" />
                        {isSelected ? 'Reset Scenario' : 'Launch Simulation'}
                      </button>

                      {/* Educational Highlights */}
                      <div style={{
                        marginTop: '4px',
                        padding: '10px',
                        borderRadius: '8px',
                        background: 'rgba(0, 0, 0, 0.25)',
                        border: '1px solid rgba(255, 255, 255, 0.03)',
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '5px', marginBottom: '6px' }}>
                          <Info size={11} color="#818cf8" />
                          <span style={{ fontSize: '9px', fontWeight: 800, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Key Concepts</span>
                        </div>
                        <ul style={{ margin: 0, paddingLeft: '14px', display: 'flex', flexDirection: 'column', gap: '5px' }}>
                          {ex.config.metadata.educationalNotes.map((note: any, idx: any) => (
                            <li key={idx} style={{ fontSize: '10px', color: '#cbd5e1', lineHeight: '1.4' }}>{note}</li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  );
                })}
            </div>
          </div>
        )}
      </aside>

      {/* ── Canvas ─────────────────────────────────────────── */}
      <div
        ref={canvasWrapRef}
        style={{
          ...S.canvasWrap,
          outline: isOverCanvas ? '2px dashed rgba(99,102,241,0.6)' : 'none',
          outlineOffset: '-3px',
        }}
      >
        <div style={S.dotGrid} />
        <div
          ref={mountRef}
          style={{
            ...S.mount,
            bottom: bottomPanelOpen ? 110 : 0,
            transition: 'bottom 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
          }}
        />

        {/* Viewport Control HUD removed as requested - zoom/pan is controlled directly by the mouse wheel and dragging */}

        {/* Floating Sidebar Toggle Buttons */}
        <button
          onClick={() => setLeftPanelOpen((open) => { const next = !open; if (next && isMobile) setRightPanelOpen(false); return next; })}
          style={{
            position: 'absolute',
            left: leftPanelOpen && isMobile ? 302 : 14,
            top: '50%',
            transform: 'translateY(-50%)',
            zIndex: 350,
            width: 32,
            height: 32,
            borderRadius: '50%',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            background: 'rgba(15, 23, 42, 0.65)',
            color: '#a5b4fc',
            backdropFilter: 'blur(8px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
            transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
            outline: 'none',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'rgba(99, 102, 241, 0.85)';
            e.currentTarget.style.color = '#ffffff';
            e.currentTarget.style.transform = 'translateY(-50%) scale(1.1)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'rgba(15, 23, 42, 0.65)';
            e.currentTarget.style.color = '#a5b4fc';
            e.currentTarget.style.transform = 'translateY(-50%) scale(1)';
          }}
          title={leftPanelOpen ? 'Collapse Left Panel' : 'Expand Left Panel'}
        >
          {leftPanelOpen ? <ChevronLeft size={16} /> : <ChevronRight size={16} />}
        </button>

        <button
          onClick={() => setRightPanelOpen((open) => { const next = !open; if (next && isMobile) setLeftPanelOpen(false); return next; })}
          style={{
            position: 'absolute',
            right: rightPanelOpen && isMobile ? 334 : 14,
            top: '50%',
            transform: 'translateY(-50%)',
            zIndex: 350,
            width: 32,
            height: 32,
            borderRadius: '50%',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            background: 'rgba(15, 23, 42, 0.65)',
            color: '#a5b4fc',
            backdropFilter: 'blur(8px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
            transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
            outline: 'none',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'rgba(99, 102, 241, 0.85)';
            e.currentTarget.style.color = '#ffffff';
            e.currentTarget.style.transform = 'translateY(-50%) scale(1.1)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'rgba(15, 23, 42, 0.65)';
            e.currentTarget.style.color = '#a5b4fc';
            e.currentTarget.style.transform = 'translateY(-50%) scale(1)';
          }}
          title={rightPanelOpen ? 'Collapse Right Panel' : 'Expand Right Panel'}
        >
          {rightPanelOpen ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>

        {/* Asset drag-over visual highlight — pointer events always off, window listener handles the drop */}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            zIndex: 210,
            pointerEvents: 'none',
            background: assetDragOver ? 'rgba(120,140,255,0.07)' : 'transparent',
            border: assetDragOver ? '2px dashed rgba(120,140,255,0.55)' : 'none',
            borderRadius: 12,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'background 0.15s, border 0.15s',
          }}
        >
          {assetDragOver && (
            <span style={{
              fontSize: 14, fontWeight: 700, color: '#a5b4fc',
              background: 'rgba(10,15,35,0.7)',
              padding: '8px 20px', borderRadius: 10,
              boxShadow: '0 4px 16px rgba(90,120,255,0.3)',
              fontFamily: "'Inter', sans-serif",
              pointerEvents: 'none',
            }}>Drop to spawn ✦</span>
          )}
        </div>

        {/* Floating Asset Library Panel */}
        <FloatingAssetPanel
          onAssetDrop={handleAssetDrop}
          canvasRef={mountRef}
        />

        {/* Drop hint overlay */}
        {isOverCanvas && (
          <div style={S.dropHint}>
            {hoveredBodyId ? (
              <span>Connect <span style={{ color: '#818cf8', fontWeight: 'bold' }}>{panelDragRef.current}</span> to <span style={{ color: '#fb7185', fontWeight: 'bold' }}>{hoveredBodyId}</span></span>
            ) : (
              <span>Release to drop <span style={{ color: '#a5b4fc', fontWeight: 'bold' }}>new {panelDragRef.current}</span></span>
            )}
          </div>
        )}

        <div style={{ ...S.badge, bottom: bottomPanelOpen ? 124 : 14, transition: 'bottom 0.3s cubic-bezier(0.4, 0, 0.2, 1)' }}>
          <span style={{ ...S.dot, background: '#6366f1', marginRight: 6 }} />
          Drag shapes & constraints · Drop anywhere
        </div>

        {/* Persistent Bottom Observables & Telemetry Dock */}
        <div style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          height: bottomPanelOpen ? '110px' : '0px',
          background: 'rgba(15, 23, 42, 0.92)',
          backdropFilter: 'blur(20px)',
          borderTop: bottomPanelOpen ? '1px solid rgba(255, 255, 255, 0.08)' : '0px solid transparent',
          display: 'flex',
          alignItems: 'stretch',
          zIndex: 340,
          fontFamily: '"Plus Jakarta Sans", system-ui, sans-serif',
          color: '#cbd5e1',
          userSelect: 'none',
          overflow: 'hidden',
          boxShadow: '0 -8px 30px rgba(0, 0, 0, 0.4)',
          transition: 'height 0.3s cubic-bezier(0.4, 0, 0.2, 1), border-top-width 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
        }}>
          {/* Collapse Button */}
          <button
            onClick={() => setBottomPanelOpen(false)}
            style={{
              position: 'absolute',
              top: 8,
              right: 8,
              width: 22,
              height: 22,
              borderRadius: 6,
              background: 'rgba(255, 255, 255, 0.06)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#94a3b8',
              fontSize: 12,
              fontWeight: 700,
              transition: 'all 0.15s',
              zIndex: 10,
              outline: 'none',
            }}
            onMouseOver={e => { e.currentTarget.style.background = 'rgba(255, 255, 255, 0.12)'; }}
            onMouseOut={e => { e.currentTarget.style.background = 'rgba(255, 255, 255, 0.06)'; }}
            title="Hide Telemetry"
          >
            ▼
          </button>

          {/* Global Clock & Mode */}
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            padding: '0 20px',
            borderRight: '1px solid rgba(255, 255, 255, 0.08)',
            background: 'rgba(0, 0, 0, 0.2)',
            minWidth: '170px',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '2px' }}>
              <span style={{
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                background: running ? '#10b981' : '#f59e0b',
                boxShadow: running ? '0 0 8px #10b981' : '0 0 8px #f59e0b'
              }} />
              <span style={{ fontSize: '8px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#64748b' }}>Simulation Time</span>
            </div>
            <span style={{ fontSize: '18px', fontWeight: 900, color: '#818cf8', fontFamily: 'monospace', textShadow: '0 0 10px rgba(129, 140, 248, 0.3)' }}>
              {formatTime(simTimeRef.current)}
            </span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginTop: '4px' }}>
              <span style={{
                fontSize: '8px',
                fontWeight: 800,
                padding: '2px 6px',
                borderRadius: '4px',
                textTransform: 'uppercase',
                background: gravityMode === 'radial' ? 'rgba(167, 139, 250, 0.15)' : 'rgba(14, 165, 233, 0.15)',
                color: gravityMode === 'radial' ? '#c084fc' : '#38bdf8',
              }}>
                {gravityMode === 'radial' ? '🌌 Orbital Gravity' : '🍎 Linear Gravity'}
              </span>
            </div>
          </div>

          {/* Active Bodies Telemetry Scroll View */}
          <div style={{
            display: 'flex',
            gap: '12px',
            padding: '12px 40px 12px 16px',
            overflowX: 'auto',
            flex: 1,
            alignItems: 'center',
            scrollbarWidth: 'thin',
          }}>
            {(storeRef.current?.getAllObjects().filter(o => !o.body.isStatic) ?? []).map(obj => {
              const isSelected = selected?.id === obj.id;
              const m = obj.body.mass;
              const speed = Math.hypot(obj.body.velocity.x, obj.body.velocity.y);
              const ke = 0.5 * m * speed * speed;

              const radialGravity = runtimeRef.current?.gravitySystem?.getRadialGravity();
              const sources = radialGravity?.getSources() ?? [];
              const G = radialGravity?.getConfig()?.gravitationalConstant ?? 0.0012;
              const bodyPos = obj.body.position;

              let centralSource: any = null;
              let minDistance = Infinity;

              for (const source of sources) {
                if (source.id === obj.id || !source.enabled) continue;
                const dist = Math.hypot(source.position.x - bodyPos.x, source.position.y - bodyPos.y);
                if (dist < minDistance) {
                  minDistance = dist;
                  centralSource = source;
                }
              }

              let pe = 0;
              let totalEnergy = ke;
              let angularMomentum = 0;

              if (centralSource) {
                const r = Math.max(0.1, Math.hypot(bodyPos.x - centralSource.position.x, bodyPos.y - centralSource.position.y));
                const M = centralSource.mass * (centralSource.metadata?.gravityStrength ?? 1.0);
                pe = - (G * M * m) / (r / 100);
                totalEnergy = ke + pe;
                angularMomentum = m * ((bodyPos.x - centralSource.position.x) * obj.body.velocity.y - (bodyPos.y - centralSource.position.y) * obj.body.velocity.x);
              }

              return (
                <div
                  key={obj.id}
                  onClick={() => {
                    setSelected(obj);
                    storeRef.current?.setSelectedObject(obj.id);
                  }}
                  style={{
                    minWidth: '220px',
                    background: isSelected ? 'rgba(99, 102, 241, 0.15)' : 'rgba(0, 0, 0, 0.3)',
                    border: isSelected ? '1px solid rgba(99, 102, 241, 0.6)' : '1px solid rgba(255, 255, 255, 0.06)',
                    borderRadius: '10px',
                    padding: '8px 12px',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                    boxShadow: isSelected ? '0 0 15px rgba(99, 102, 241, 0.2)' : 'none',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '4px',
                  }}
                >
                  {/* Header */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: '11px', fontWeight: 800, color: isSelected ? '#a5b4fc' : '#cbd5e1', fontFamily: 'monospace' }}>
                      🛰️ {obj.id.replace('example-', '').replace('orbit-', '')}
                    </span>
                    <span style={{
                      fontSize: '8px',
                      fontWeight: 700,
                      textTransform: 'uppercase',
                      color: isSelected ? '#6ee7b7' : '#94a3b8',
                      background: isSelected ? 'rgba(16, 185, 129, 0.15)' : 'rgba(255, 255, 255, 0.04)',
                      padding: '1px 4px',
                      borderRadius: '4px'
                    }}>
                      {obj.body.isStatic ? 'Static' : 'Dynamic'}
                    </span>
                  </div>

                  {/* Real-time stats */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px', marginTop: '2px' }}>
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                      <span style={{ fontSize: '7px', color: '#64748b', textTransform: 'uppercase', fontWeight: 700 }}>Kinetic (K)</span>
                      <span style={{ fontSize: '10px', color: '#38bdf8', fontFamily: 'monospace', fontWeight: 600 }}>
                        {formatScientific(ke * 10, 'GJ')}
                      </span>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                      <span style={{ fontSize: '7px', color: '#64748b', textTransform: 'uppercase', fontWeight: 700 }}>Potential (U)</span>
                      <span style={{ fontSize: '10px', color: '#fb7185', fontFamily: 'monospace', fontWeight: 600 }}>
                        {gravityMode === 'radial' && centralSource ? formatScientific(pe * 10, 'GJ') : '0.00 GJ'}
                      </span>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                      <span style={{ fontSize: '7px', color: '#64748b', textTransform: 'uppercase', fontWeight: 700 }}>Total (E)</span>
                      <span style={{ fontSize: '10px', color: '#a78bfa', fontFamily: 'monospace', fontWeight: 600 }}>
                        {gravityMode === 'radial' && centralSource ? formatScientific(totalEnergy * 10, 'GJ') : formatScientific(ke * 10, 'GJ')}
                      </span>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                      <span style={{ fontSize: '7px', color: '#64748b', textTransform: 'uppercase', fontWeight: 700 }}>Ang Momentum</span>
                      <span style={{ fontSize: '10px', color: '#fde047', fontFamily: 'monospace', fontWeight: 600 }}>
                        {gravityMode === 'radial' && centralSource ? formatScientific(angularMomentum * 10, 'kg·m²/s') : 'N/A'}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}

            {(storeRef.current?.getAllObjects().filter(o => !o.body.isStatic) ?? []).length === 0 && (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 1, height: '100%' }}>
                <span style={{ fontSize: '11px', color: '#475569', fontStyle: 'italic' }}>
                  🚀 Spawn orbiting satellites or planets to view live telemetry readouts.
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Floating Expand Button when Collapsed */}
        {!bottomPanelOpen && (
          <button
            onClick={() => setBottomPanelOpen(true)}
            style={{
              position: 'absolute',
              bottom: 14,
              left: '50%',
              transform: 'translateX(-50%)',
              padding: '6px 16px',
              borderRadius: '999px',
              background: 'rgba(15, 23, 42, 0.85)',
              backdropFilter: 'blur(16px)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              color: '#c7d2fe',
              fontSize: '11px',
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              boxShadow: '0 4px 20px rgba(0,0,0,0.4)',
              zIndex: 340,
              transition: 'all 0.2s ease',
              outline: 'none',
            }}
            onMouseOver={e => {
              e.currentTarget.style.background = 'rgba(99, 102, 241, 0.85)';
              e.currentTarget.style.color = '#ffffff';
              e.currentTarget.style.transform = 'translateX(-50%) scale(1.05)';
            }}
            onMouseOut={e => {
              e.currentTarget.style.background = 'rgba(15, 23, 42, 0.85)';
              e.currentTarget.style.color = '#c7d2fe';
              e.currentTarget.style.transform = 'translateX(-50%) scale(1)';
            }}
          >
            📊 Show Telemetry
          </button>
        )}





        {/* Circular Floating AI Toggle Button */}
        <motion.button
          onClick={() => setTutorEnabled(!tutorEnabled)}
          whileHover={{ scale: 1.08 }}
          whileTap={{ scale: 0.95 }}
          style={{
            position: 'absolute',
            top: 20,
            right: 20,
            zIndex: 390,
            width: 46,
            height: 46,
            borderRadius: '50%',
            background: tutorEnabled
              ? 'linear-gradient(135deg, #1e1b4b 0%, #0f172a 100%)'
              : 'rgba(15, 23, 42, 0.65)',
            border: tutorEnabled
              ? '2px solid #5B5FFF'
              : '1px solid rgba(255, 255, 255, 0.08)',
            boxShadow: tutorEnabled
              ? '0 0 16px rgba(91, 95, 255, 0.55), 0 4px 12px rgba(0, 0, 0, 0.3)'
              : '0 4px 12px rgba(0, 0, 0, 0.35)',
            backdropFilter: 'blur(12px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            transition: 'border 0.25s, background 0.25s, box-shadow 0.25s',
            outline: 'none',
          }}
          title={tutorEnabled ? 'Close AI explanation panel' : 'Open AI explanation panel'}
        >
          <Sparkles
            size={20}
            color="#fbbf24"
            style={{
              animation: tutorEnabled ? 'pulse-glow 1.8s infinite ease-in-out' : 'none',
              transform: tutorEnabled ? 'scale(1.05)' : 'none',
              transition: 'transform 0.2s'
            }}
          />

          {/* Glowing Notification Dot for queued events */}
          {queueCount > 0 && (
            <span style={{
              position: 'absolute',
              top: 2,
              right: 2,
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: '#ec4899', // Pink glow
              border: '1.5px solid #0f172a',
              boxShadow: '0 0 6px #ec4899',
              display: 'block'
            }} />
          )}
        </motion.button>

        {/* Floating AI Response Panel — hidden when tutor is off */}
        <AnimatePresence mode="wait">
          {tutorEnabled && currentExplanation && (
            /* Expanded Full Workspace AI Inspector Panel */
            <motion.div
              key="tutor-expanded"
              initial={{ opacity: 0, y: 15, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 15, scale: 0.95 }}
              transition={{ type: 'spring', damping: 22, stiffness: 200 }}
              onMouseEnter={() => setIsHovered(true)}
              onMouseLeave={() => setIsHovered(false)}
              style={{
                position: 'absolute',
                top: 20,
                right: 84,
                zIndex: 380,
                width: tutorMaximized ? 480 : tutorWidth,
                height: tutorMinimized ? 'auto' : (tutorMaximized ? 'calc(100% - 40px)' : tutorHeight),
                maxHeight: 'calc(100% - 40px)',
                background: 'linear-gradient(180deg, #0B1020, #121933)',
                backdropFilter: 'blur(20px)',
                border: '1px solid rgba(120, 120, 255, 0.15)',
                borderRadius: 20,
                padding: '16px 16px 18px 16px',
                boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4), inset 0 1px 1px rgba(255, 255, 255, 0.05)',
                color: '#f8fafc',
                display: 'flex',
                flexDirection: 'column',
                gap: 12,
                overflow: 'hidden',
                transition: 'width 0.3s ease, height 0.3s ease',
              }}
            >
              {/* CSS Glow Animations Injector */}
              <style dangerouslySetInnerHTML={{
                __html: `
                @keyframes shimmer {
                  0% { background-position: -200% 0; }
                  100% { background-position: 200% 0; }
                }
                @keyframes pulse-glow {
                  0%, 100% { transform: scale(1); opacity: 0.6; filter: drop-shadow(0 0 1px rgba(120, 120, 255, 0.4)); }
                  50% { transform: scale(1.1); opacity: 1; filter: drop-shadow(0 0 6px rgba(120, 120, 255, 0.8)); }
                }
                .shimmer-bg {
                  background: linear-gradient(90deg, rgba(255,255,255,0.03) 25%, rgba(255,255,255,0.1) 50%, rgba(255,255,255,0.03) 75%);
                  background-size: 200% 100%;
                  animation: shimmer 1.5s infinite linear;
                }
                .hover-glow-left {
                  transition: background-color 0.2s, box-shadow 0.2s;
                }
                .hover-glow-left:hover {
                  background-color: rgba(120, 120, 255, 0.2);
                  box-shadow: 2px 0 10px rgba(120, 120, 255, 0.4);
                }
                .hover-glow-bottom {
                  transition: background-color 0.2s, box-shadow 0.2s;
                }
                .hover-glow-bottom:hover {
                  background-color: rgba(120, 120, 255, 0.2);
                  box-shadow: 0 -2px 10px rgba(120, 120, 255, 0.4);
                }
                .tutor-scroll-container::-webkit-scrollbar {
                  width: 4px;
                }
                .tutor-scroll-container::-webkit-scrollbar-track {
                  background: transparent;
                }
                .tutor-scroll-container::-webkit-scrollbar-thumb {
                  background: rgba(255, 255, 255, 0.08);
                  border-radius: 4px;
                }
                .tutor-scroll-container::-webkit-scrollbar-thumb:hover {
                  background: rgba(120, 120, 255, 0.35);
                }
              ` }} />

              {/* Resizer Handle Left Edge (Horizontal) */}
              {!tutorMinimized && !tutorMaximized && (
                <div
                  style={{
                    position: 'absolute',
                    left: 0,
                    top: 0,
                    bottom: 0,
                    width: 6,
                    cursor: 'w-resize',
                    zIndex: 210,
                  }}
                  onPointerDown={handleResizeLeft}
                  className="hover-glow-left"
                  title="Drag to resize width"
                />
              )}

              {/* Resize Handle Bottom Edge (Vertical) */}
              {!tutorMinimized && !tutorMaximized && (
                <div
                  style={{
                    position: 'absolute',
                    left: 0,
                    right: 0,
                    bottom: 0,
                    height: 6,
                    cursor: 's-resize',
                    zIndex: 210,
                  }}
                  onPointerDown={handleResizeBottom}
                  className="hover-glow-bottom"
                  title="Drag to resize height"
                />
              )}

              {/* Premium Sticky Header */}
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                borderBottom: '1px solid rgba(255,255,255,0.08)',
                paddingBottom: 10,
                flexShrink: 0,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Sparkles size={16} color="#fbbf24" className="pulse-svg" style={{ animation: 'pulse-glow 1.8s infinite ease-in-out' }} />
                  <span style={{ fontSize: 13.5, fontWeight: 800, color: '#ffffff', letterSpacing: '0.02em', fontFamily: "'Plus Jakarta Sans', system-ui, sans-serif" }}>
                    AI Explanation
                  </span>

                  {/* Violet Queue Badge */}
                  <span style={{
                    background: '#5B5FFF',
                    color: '#ffffff',
                    fontSize: 10,
                    fontWeight: 800,
                    padding: '2px 8px',
                    borderRadius: 12,
                    marginLeft: 4,
                    boxShadow: '0 0 8px rgba(91, 95, 255, 0.4)'
                  }}>
                    {queueCount > 0 ? `+${queueCount}` : '+1'}
                  </span>

                  {/* Next explanation navigation button */}
                  {queueCount > 0 && (
                    <button
                      onClick={handleNext}
                      style={{
                        background: 'rgba(91, 95, 255, 0.25)',
                        border: '1px solid rgba(91, 95, 255, 0.45)',
                        borderRadius: 12,
                        padding: '2px 8.5px',
                        color: '#ffffff',
                        fontSize: 10,
                        fontWeight: 800,
                        marginLeft: 6,
                        cursor: 'pointer',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 3,
                        boxShadow: '0 0 8px rgba(91, 95, 255, 0.3)',
                        transition: 'all 0.2s',
                        outline: 'none',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = 'rgba(91, 95, 255, 0.4)';
                        e.currentTarget.style.borderColor = 'rgba(91, 95, 255, 0.6)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = 'rgba(91, 95, 255, 0.25)';
                        e.currentTarget.style.borderColor = 'rgba(91, 95, 255, 0.45)';
                      }}
                      title="View next queued physics explanation"
                    >
                      <span>Next</span>
                      <ChevronRight size={10} strokeWidth={3} />
                    </button>
                  )}
                </div>

                {/* Window Controls Button Group */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  {/* Pin button */}
                  <button
                    onClick={() => setTutorPinned(!tutorPinned)}
                    style={{
                      background: tutorPinned ? 'rgba(91, 95, 255, 0.2)' : 'transparent',
                      border: 'none',
                      cursor: 'pointer',
                      color: tutorPinned ? '#a5b4fc' : '#94a3b8',
                      width: 24,
                      height: 24,
                      borderRadius: '50%',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      transition: 'all 0.2s',
                      outline: 'none',
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.color = '#ffffff'}
                    onMouseLeave={(e) => e.currentTarget.style.color = tutorPinned ? '#a5b4fc' : '#94a3b8'}
                    title={tutorPinned ? "Dock Floating (Auto-Dismiss Enabled)" : "Pin Inspector (Disable Auto-Dismiss)"}
                  >
                    <Pin size={13} style={{ transform: tutorPinned ? 'rotate(45deg)' : 'none' }} />
                  </button>
                  {/* Maximize button */}
                  <button
                    onClick={() => setTutorMaximized(!tutorMaximized)}
                    style={{
                      background: tutorMaximized ? 'rgba(91, 95, 255, 0.15)' : 'transparent',
                      border: 'none',
                      cursor: 'pointer',
                      color: tutorMaximized ? '#ffffff' : '#94a3b8',
                      width: 24,
                      height: 24,
                      borderRadius: '50%',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      transition: 'all 0.2s',
                      outline: 'none',
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.color = '#ffffff'}
                    onMouseLeave={(e) => e.currentTarget.style.color = tutorMaximized ? '#ffffff' : '#94a3b8'}
                    title={tutorMaximized ? "Restore Layout" : "Maximize Panel"}
                  >
                    <Maximize2 size={13} />
                  </button>
                  {/* Minimize arrow (chevron down) */}
                  <button
                    onClick={() => setTutorMinimized(!tutorMinimized)}
                    style={{
                      background: 'transparent',
                      border: 'none',
                      cursor: 'pointer',
                      color: '#94a3b8',
                      width: 24,
                      height: 24,
                      borderRadius: '50%',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      transition: 'all 0.2s',
                      outline: 'none',
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.color = '#ffffff'}
                    onMouseLeave={(e) => e.currentTarget.style.color = '#94a3b8'}
                    title={tutorMinimized ? "Expand Panel" : "Minimize Panel"}
                  >
                    {tutorMinimized ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                  </button>
                  {/* Close button */}
                  <button
                    onClick={() => {
                      handleClear();
                      setTutorEnabled(false);
                    }}
                    style={{
                      background: 'transparent',
                      border: 'none',
                      cursor: 'pointer',
                      color: '#94a3b8',
                      width: 24,
                      height: 24,
                      borderRadius: '50%',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      transition: 'all 0.2s',
                      outline: 'none',
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.color = '#ef4444'}
                    onMouseLeave={(e) => e.currentTarget.style.color = '#94a3b8'}
                    title="Close and dismiss explanation panel"
                  >
                    <X size={14} />
                  </button>
                </div>
              </div>

              {/* Animated Pill Tabs */}
              <div style={{
                display: 'flex',
                background: 'rgba(0, 0, 0, 0.35)',
                borderRadius: 30,
                padding: 4,
                border: '1px solid rgba(255, 255, 255, 0.05)',
                gap: 4,
                flexShrink: 0
              }}>
                {(['explanation', 'effects', 'formula'] as const).map((tab) => {
                  const isActive = activeTab === tab;
                  return (
                    <button
                      key={tab}
                      onClick={() => setActiveTab(tab)}
                      style={{
                        flex: 1,
                        background: isActive ? 'linear-gradient(90deg, #5B5FFF, #7B61FF)' : 'transparent',
                        color: isActive ? '#ffffff' : '#94a3b8',
                        border: 'none',
                        borderRadius: 20,
                        padding: '6px 0',
                        fontSize: 12,
                        fontWeight: 600,
                        letterSpacing: '0.02em',
                        cursor: 'pointer',
                        boxShadow: isActive ? '0 0 12px rgba(91, 95, 255, 0.4)' : 'none',
                        transition: 'all 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
                        outline: 'none',
                        fontFamily: "'Plus Jakarta Sans', system-ui, sans-serif"
                      }}
                      onMouseEnter={(e) => {
                        if (!isActive) {
                          e.currentTarget.style.color = '#cbd5e1';
                        } else {
                          e.currentTarget.style.filter = 'brightness(1.15)';
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (!isActive) {
                          e.currentTarget.style.color = '#94a3b8';
                        } else {
                          e.currentTarget.style.filter = 'none';
                        }
                      }}
                    >
                      {tab.charAt(0).toUpperCase() + tab.slice(1)}
                    </button>
                  );
                })}
              </div>

              {/* Independent Scrollable Content Area */}
              {!tutorMinimized && (
                <div
                  className="tutor-scroll-container"
                  style={{
                    flex: 1,
                    overflowY: 'auto',
                    paddingRight: 4,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 12,
                  }}
                >
                  {currentExplanation.loading ? (
                    /* Sleek glassmorphic shimmering loader */
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10, padding: 8 }}>
                      <div className="shimmer-bg" style={{ height: 20, width: '70%', borderRadius: 6 }} />
                      <div className="shimmer-bg" style={{ height: 60, width: '100%', borderRadius: 8 }} />
                      <div className="shimmer-bg" style={{ height: 60, width: '100%', borderRadius: 8 }} />
                      <div className="shimmer-bg" style={{ height: 60, width: '100%', borderRadius: 8 }} />
                    </div>
                  ) : (
                    <>
                      {/* Active Tab View Router */}
                      {activeTab === 'explanation' && (() => {
                        const sections = parseExplanationText(currentExplanation.insight.explanation);
                        const getParsedSection = (queryKey: string) => {
                          const keys = Object.keys(sections);
                          const foundKey = keys.find(k => k.includes(queryKey) || queryKey.includes(k));
                          return foundKey ? sections[foundKey] : null;
                        };

                        let step1Text = getParsedSection('EXPLANATION') || getParsedSection('LIVE') || getParsedSection('HAPPENED') || getParsedSection('STEP 1');
                        let step2Text = getParsedSection('UNDERSTANDING') || getParsedSection('DEEPER') || getParsedSection('CHANGED') || getParsedSection('STEP 2');
                        let step3Text = getParsedSection('WHY') || getParsedSection('STEP 3');
                        let step4Text = getParsedSection('NOTICE') || getParsedSection('STEP 4');

                        if (!step1Text && !step2Text && !step3Text && !step4Text) {
                          // Offline fallback: split by sentences and distribute across steps
                          const rawExp = currentExplanation.insight.explanation || '';
                          const sentences = rawExp.split(/[.!?]+\s+/).filter(Boolean);
                          step1Text = sentences[0] || "The Earth object is now attached to the pendulum.";
                          step2Text = sentences[1] || "The pendulum has more mass and swings with greater weight.";
                          step3Text = sentences[2] || "Adding the Earth increases the total mass, so gravity pulls it down more strongly.";
                          step4Text = sentences[3] || sentences.slice(3).join('. ') || "Watch how the pendulum swings slower and with more force compared to before.";
                        }

                        return (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                            <StepCard num={1} title="What Happened" description={step1Text || ''} type="blue" />
                            <StepCard num={2} title="What Changed" description={step2Text || ''} type="green" />
                            <StepCard num={3} title="Simple Why" description={step3Text || ''} type="orange" />
                            <StepCard num={4} title="What to Notice" description={step4Text || ''} type="purple" />

                            {/* Key Effects Section inside the Explanation tab */}
                            <div style={{ marginTop: 14, borderTop: '1px solid rgba(255, 255, 255, 0.05)', paddingTop: 14 }}>
                              <span style={{ fontSize: 12, fontWeight: 700, color: '#7B61FF', letterSpacing: '0.02em', display: 'block', marginBottom: 8, fontFamily: "'Plus Jakarta Sans', system-ui, sans-serif" }}>
                                Key Effects
                              </span>
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                                {(currentExplanation.insight.effects && currentExplanation.insight.effects.length > 0
                                  ? currentExplanation.insight.effects
                                  : ['Greater gravitational force', 'Slower swing', 'More inertia', 'More kinetic energy at the bottom']
                                ).map((effect, idx) => {
                                  const cleanedEffect = effect.replace(/^[^\w\s]+/g, '').trim();
                                  return (
                                    <motion.span
                                      key={idx}
                                      whileHover={{ scale: 1.04, borderColor: '#7B61FF' }}
                                      style={{
                                        fontSize: 11,
                                        padding: '5px 12px',
                                        borderRadius: 20,
                                        background: 'rgba(255, 255, 255, 0.03)',
                                        border: '1px solid rgba(123, 97, 255, 0.25)',
                                        boxShadow: '0 0 8px rgba(123, 97, 255, 0.08)',
                                        color: '#cbd5e1',
                                        cursor: 'default',
                                        transition: 'all 0.2s',
                                        display: 'inline-flex',
                                        alignItems: 'center',
                                      }}
                                    >
                                      {cleanedEffect}
                                    </motion.span>
                                  );
                                })}
                              </div>
                            </div>
                          </div>
                        );
                      })()}

                      {activeTab === 'effects' && (() => {
                        const hasSelected = !!selected;
                        const body = selected?.body;

                        return (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                            {/* Live Telemetry Table */}
                            <div style={{
                              background: 'rgba(0, 0, 0, 0.25)',
                              border: '1px solid rgba(255, 255, 255, 0.05)',
                              borderRadius: 12,
                              padding: 10,
                            }}>
                              <span style={{ fontSize: 9.5, fontWeight: 800, color: '#38bdf8', textTransform: 'uppercase', letterSpacing: '0.06em', display: 'block', marginBottom: 8 }}>
                                🛰️ Active Simulation Telemetry
                              </span>
                              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
                                <div style={{ background: 'rgba(255, 255, 255, 0.01)', border: '1px solid rgba(255, 255, 255, 0.03)', borderRadius: 8, padding: '6px 8px', display: 'flex', flexDirection: 'column' }}>
                                  <span style={{ fontSize: 7.5, color: '#64748b', textTransform: 'uppercase', fontWeight: 800 }}>Target</span>
                                  <span style={{ fontSize: 11, fontWeight: 700, color: hasSelected ? '#f87171' : '#64748b', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>
                                    {hasSelected ? (body?.label || selected.id) : 'None'}
                                  </span>
                                </div>
                                <div style={{ background: 'rgba(255, 255, 255, 0.01)', border: '1px solid rgba(255, 255, 255, 0.03)', borderRadius: 8, padding: '6px 8px', display: 'flex', flexDirection: 'column' }}>
                                  <span style={{ fontSize: 7.5, color: '#64748b', textTransform: 'uppercase', fontWeight: 800 }}>Gravity Mode</span>
                                  <span style={{ fontSize: 11, fontWeight: 700, color: '#38bdf8' }}>
                                    {gravityMode === 'radial' ? '🌌 Radial' : '🍎 Downward'}
                                  </span>
                                </div>
                                <div style={{ background: 'rgba(255, 255, 255, 0.01)', border: '1px solid rgba(255, 255, 255, 0.03)', borderRadius: 8, padding: '6px 8px', display: 'flex', flexDirection: 'column' }}>
                                  <span style={{ fontSize: 7.5, color: '#64748b', textTransform: 'uppercase', fontWeight: 800 }}>Bodies</span>
                                  <span style={{ fontSize: 11, fontWeight: 700, color: '#34d399' }}>{bodyCount} shapes</span>
                                </div>
                                <div style={{ background: 'rgba(255, 255, 255, 0.01)', border: '1px solid rgba(255, 255, 255, 0.03)', borderRadius: 8, padding: '6px 8px', display: 'flex', flexDirection: 'column' }}>
                                  <span style={{ fontSize: 7.5, color: '#64748b', textTransform: 'uppercase', fontWeight: 800 }}>Speed</span>
                                  <span style={{ fontSize: 11, fontWeight: 700, color: '#fbbf24' }}>{speed.toFixed(1)}x</span>
                                </div>
                              </div>
                            </div>

                            {/* Live Target Telemetry if selected */}
                            {hasSelected && body && (
                              <div style={{
                                background: 'rgba(99, 102, 241, 0.05)',
                                border: '1px solid rgba(99, 102, 241, 0.15)',
                                borderRadius: 12,
                                padding: 10,
                              }}>
                                <span style={{ fontSize: 9.5, fontWeight: 800, color: '#a5b4fc', textTransform: 'uppercase', letterSpacing: '0.06em', display: 'block', marginBottom: 8 }}>
                                  🎯 Target Telemetry: {body.label || selected.id}
                                </span>
                                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
                                  <div style={{ background: 'rgba(255, 255, 255, 0.01)', border: '1px solid rgba(255, 255, 255, 0.03)', borderRadius: 8, padding: '6px 8px', display: 'flex', flexDirection: 'column' }}>
                                    <span style={{ fontSize: 7.5, color: '#94a3b8', textTransform: 'uppercase', fontWeight: 800 }}>Mass</span>
                                    <span style={{ fontSize: 11, fontWeight: 700, color: '#cbd5e1', fontFamily: 'monospace' }}>{body.mass.toFixed(1)} kg</span>
                                  </div>
                                  <div style={{ background: 'rgba(255, 255, 255, 0.01)', border: '1px solid rgba(255, 255, 255, 0.03)', borderRadius: 8, padding: '6px 8px', display: 'flex', flexDirection: 'column' }}>
                                    <span style={{ fontSize: 7.5, color: '#94a3b8', textTransform: 'uppercase', fontWeight: 800 }}>Speed (v)</span>
                                    <span style={{ fontSize: 11, fontWeight: 700, color: '#cbd5e1', fontFamily: 'monospace' }}>
                                      {Math.hypot(body.velocity.x, body.velocity.y).toFixed(1)} m/s
                                    </span>
                                  </div>
                                  <div style={{ background: 'rgba(255, 255, 255, 0.01)', border: '1px solid rgba(255, 255, 255, 0.03)', borderRadius: 8, padding: '6px 8px', display: 'flex', flexDirection: 'column' }}>
                                    <span style={{ fontSize: 7.5, color: '#94a3b8', textTransform: 'uppercase', fontWeight: 800 }}>Bounciness (e)</span>
                                    <span style={{ fontSize: 11, fontWeight: 700, color: '#cbd5e1', fontFamily: 'monospace' }}>{body.restitution.toFixed(2)}</span>
                                  </div>
                                  <div style={{ background: 'rgba(255, 255, 255, 0.01)', border: '1px solid rgba(255, 255, 255, 0.03)', borderRadius: 8, padding: '6px 8px', display: 'flex', flexDirection: 'column' }}>
                                    <span style={{ fontSize: 7.5, color: '#94a3b8', textTransform: 'uppercase', fontWeight: 800 }}>Friction (μ)</span>
                                    <span style={{ fontSize: 11, fontWeight: 700, color: '#cbd5e1', fontFamily: 'monospace' }}>{body.friction.toFixed(2)}</span>
                                  </div>
                                </div>
                              </div>
                            )}

                            {/* Suggested Experiments */}
                            <div>
                              <span style={{ fontSize: 9.5, fontWeight: 800, color: '#fbbf24', textTransform: 'uppercase', letterSpacing: '0.06em', display: 'block', marginBottom: 6 }}>
                                🧪 Sandbox Experiments
                              </span>
                              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                                {currentExplanation.insight.suggestions && currentExplanation.insight.suggestions.length > 0 ? (
                                  currentExplanation.insight.suggestions.map((sug, i) => (
                                    <motion.button
                                      key={i}
                                      whileHover={{ scale: 1.02, x: 4, background: 'rgba(251, 191, 36, 0.12)' }}
                                      onClick={() => {
                                        const q = `Help me perform the suggested experiment: ${sug}`;
                                        setAiPrompt(q);
                                        handleAiQuery(q);
                                      }}
                                      style={{
                                        background: 'rgba(255, 255, 255, 0.02)',
                                        border: '1px solid rgba(251, 191, 36, 0.25)',
                                        borderRadius: 8,
                                        padding: '8px 12px',
                                        fontSize: 11,
                                        fontWeight: 600,
                                        color: '#fde047',
                                        textAlign: 'left',
                                        cursor: 'pointer',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'space-between',
                                        transition: 'all 0.2s',
                                        outline: 'none',
                                      }}
                                    >
                                      <span>👉 {sug}</span>
                                      <span style={{ fontSize: 8, opacity: 0.6, letterSpacing: '0.05em', textTransform: 'uppercase' }}>Launch</span>
                                    </motion.button>
                                  ))
                                ) : (
                                  <span style={{ fontSize: 10.5, color: '#64748b', fontStyle: 'italic' }}>No suggested experiments.</span>
                                )}
                              </div>
                            </div>
                          </div>
                        );
                      })()}

                      {activeTab === 'formula' && (() => {
                        const rawFormula = currentExplanation.insight.formula || '';

                        const getFormattedFormula = (formula: string) => {
                          if (!formula) return 'No formula identified';
                          if (formula.includes('$')) return formula;
                          return `$$${formula.replace(/×/g, '\\times').replace(/\*/g, '\\cdot')}$$`;
                        };

                        const getFormulaContext = (formula: string) => {
                          const f = formula.toLowerCase();
                          if (f.includes('hooke') || f.includes('-kx') || f.includes('spring')) {
                            return {
                              name: "Hooke's Law (Simple Harmonic Oscillation)",
                              desc: "Hooke's Law states that the force exerted by a spring is directly proportional to its displacement from equilibrium, but in the opposite direction. This linear restoring force drives simple harmonic motion.",
                              insight: "💡 Try increasing spring stiffness (k) in the left panel — watch how the bob rebounds faster!"
                            };
                          }
                          if (f.includes('gravity') || f.includes('m × g') || f.includes('mg')) {
                            return {
                              name: "Newton's Second Law: Gravity & Weight",
                              desc: "Gravity exerts a downward force proportional to mass. In linear mode, this results in uniform downward acceleration (g ≈ 9.8 m/s² on Earth) regardless of body weight.",
                              insight: "💡 In free-fall, objects of different weights fall at the exact same rate because gravity's force scales directly with inertia!"
                            };
                          }
                          if (f.includes('momentum') || f.includes('collision') || f.includes('m1') || f.includes('mv')) {
                            return {
                              name: "Conservation of Linear Momentum",
                              desc: "During collisions, the total momentum remains constant. Any momentum lost by Object A is gained by Object B. Restitution (e) determines energy conservation.",
                              insight: "💡 Try changing Restitution (e) to 1.0 (elastic) — bodies will bounce indefinitely without energy loss!"
                            };
                          }
                          if (f.includes('pivot') || f.includes('l/g') || f.includes('pendulum')) {
                            return {
                              name: "Simple Pendulum Swing Cycle",
                              desc: "A pendulum's swing period is determined strictly by its string length (L) and the gravity constant (g). Crucially, the period is independent of bob mass!",
                              insight: "💡 Try launching a pendulum bob and changing its mass — the swing rate remains identical!"
                            };
                          }
                          return {
                            name: "Core Physics Equation",
                            desc: "This mathematical relationship governs the active sandbox state. The simulator evaluates this equation in real-time at 60 steps per second to solve body coordinates.",
                            insight: "💡 Select a shape and modify its mass or friction — watch how these immediately alter the live graphs!"
                          };
                        };

                        const context = getFormulaContext(rawFormula);

                        return (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                            {/* Premium LaTeX FormulaCard */}
                            <div style={{
                              background: 'rgba(99, 102, 241, 0.03)',
                              border: '1px solid rgba(120, 120, 255, 0.25)',
                              borderRadius: 14,
                              padding: '16px 12px',
                              boxShadow: '0 4px 16px rgba(120, 120, 255, 0.05), inset 0 1px 1px rgba(255, 255, 255, 0.05)',
                              display: 'flex',
                              flexDirection: 'column',
                              alignItems: 'center',
                              justifyContent: 'center',
                              textAlign: 'center',
                              gap: 12
                            }}>
                              <span style={{ fontSize: 9.5, fontWeight: 800, color: '#a5b4fc', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
                                {context.name}
                              </span>

                              <div style={{
                                fontSize: 16,
                                color: '#fde047',
                                fontWeight: 700,
                                margin: '8px 0',
                                width: '100%',
                                display: 'flex',
                                justifyContent: 'center'
                              }}>
                                <ReactMarkdown
                                  remarkPlugins={[remarkMath]}
                                  rehypePlugins={[rehypeKatex]}
                                  components={{
                                    p: ({ node, ...props }: any) => <p style={{ margin: 0 }} {...props} />,
                                  }}
                                >
                                  {getFormattedFormula(rawFormula)}
                                </ReactMarkdown>
                              </div>

                              <div style={{ display: 'flex', gap: 8, width: '100%' }}>
                                <motion.button
                                  whileHover={{ scale: 1.02, background: 'rgba(99, 102, 241, 0.2)' }}
                                  onClick={() => {
                                    const q = `Explain the mathematical equation "${rawFormula}" and its variables in detail.`;
                                    setAiPrompt(q);
                                    handleAiQuery(q);
                                  }}
                                  style={{
                                    flex: 1,
                                    background: 'rgba(99, 102, 241, 0.1)',
                                    border: '1px solid rgba(99, 102, 241, 0.3)',
                                    borderRadius: 8,
                                    padding: '6px 0',
                                    fontSize: 10,
                                    fontWeight: 700,
                                    color: '#cbd5e1',
                                    cursor: 'pointer',
                                    transition: 'all 0.2s',
                                    outline: 'none',
                                  }}
                                >
                                  📚 Explain Formula
                                </motion.button>
                                <motion.button
                                  whileHover={{ scale: 1.02, background: 'rgba(168, 85, 247, 0.2)' }}
                                  onClick={() => {
                                    const q = `Give me some interactive math experiments to test Hookes/Newtons laws in this Sandbox.`;
                                    setAiPrompt(q);
                                    handleAiQuery(q);
                                  }}
                                  style={{
                                    flex: 1,
                                    background: 'rgba(168, 85, 247, 0.1)',
                                    border: '1px solid rgba(168, 85, 247, 0.3)',
                                    borderRadius: 8,
                                    padding: '6px 0',
                                    fontSize: 10,
                                    fontWeight: 700,
                                    color: '#cbd5e1',
                                    cursor: 'pointer',
                                    transition: 'all 0.2s',
                                    outline: 'none',
                                  }}
                                >
                                  ⚙️ Open Formula Lab
                                </motion.button>
                              </div>
                            </div>

                            {/* Written Context */}
                            <div style={{
                              background: 'rgba(255, 255, 255, 0.02)',
                              border: '1px solid rgba(255, 255, 255, 0.04)',
                              borderRadius: 12,
                              padding: 12,
                              display: 'flex',
                              flexDirection: 'column',
                              gap: 8
                            }}>
                              <span style={{ fontSize: 9.5, fontWeight: 800, color: '#cbd5e1', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
                                Theoretical Context
                              </span>
                              <p style={{ fontSize: 11, color: '#94a3b8', lineHeight: 1.5, margin: 0 }}>
                                {context.desc}
                              </p>
                              <div style={{
                                borderTop: '1px dashed rgba(255,255,255,0.06)',
                                paddingTop: 8,
                                fontSize: 10.5,
                                color: '#fde047',
                                fontWeight: 500,
                                lineHeight: 1.45
                              }}>
                                {context.insight}
                              </div>
                            </div>
                          </div>
                        );
                      })()}
                    </>
                  )}
                </div>
              )}

              {/* Bottom Row Action Buttons */}
              {!tutorMinimized && (
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  borderTop: '1px solid rgba(255, 255, 255, 0.05)',
                  paddingTop: 12,
                  flexShrink: 0,
                  gap: 10
                }}>
                  <div style={{ display: 'flex', gap: 8, flex: 1 }}>
                    <motion.button
                      whileHover={{ scale: 1.03, boxShadow: '0 0 12px rgba(120, 120, 255, 0.25)' }}
                      onClick={() => {
                        const q = "Generate a graph analysis and explain the velocity curves of the active bodies";
                        setAiPrompt(q);
                        handleAiQuery(q);
                      }}
                      style={{
                        flex: 1,
                        background: 'rgba(255, 255, 255, 0.03)',
                        border: '1px solid rgba(255, 255, 255, 0.08)',
                        borderRadius: 10,
                        padding: '8px 12px',
                        fontSize: 11,
                        fontWeight: 700,
                        color: '#cbd5e1',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: 6,
                        cursor: 'pointer',
                        transition: 'all 0.2s',
                        outline: 'none',
                      }}
                    >
                      <LineChart size={14} color="#7B61FF" />
                      <span>Show Graph</span>
                    </motion.button>

                    <motion.button
                      whileHover={{ scale: 1.03, boxShadow: '0 0 12px rgba(168, 85, 247, 0.25)' }}
                      onClick={() => {
                        const q = "Show me the step-by-step mathematical calculations for the current event";
                        setAiPrompt(q);
                        handleAiQuery(q);
                      }}
                      style={{
                        flex: 1,
                        background: 'rgba(255, 255, 255, 0.03)',
                        border: '1px solid rgba(255, 255, 255, 0.08)',
                        borderRadius: 10,
                        padding: '8px 12px',
                        fontSize: 11,
                        fontWeight: 700,
                        color: '#cbd5e1',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: 6,
                        cursor: 'pointer',
                        transition: 'all 0.2s',
                        outline: 'none',
                      }}
                    >
                      <Cpu size={14} color="#c084fc" />
                      <span>View Calculations</span>
                    </motion.button>
                  </div>

                  {/* Diagonal Resize Grab Handle */}
                  {!tutorMaximized && (
                    <motion.div
                      whileHover={{ scale: 1.05, borderColor: 'rgba(120, 120, 255, 0.3)' }}
                      onPointerDown={handleResizeBottomLeft}
                      style={{
                        width: 34,
                        height: 34,
                        borderRadius: 8,
                        border: '1px solid rgba(255, 255, 255, 0.08)',
                        background: 'rgba(15, 23, 42, 0.6)',
                        cursor: 'sw-resize',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0,
                        transition: 'all 0.2s',
                      }}
                      title="Drag to resize panel diagonally"
                    >
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ transform: 'rotate(90deg)' }}>
                        <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" />
                      </svg>
                    </motion.div>
                  )}
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Dynamic Sandbox Validation State & Level Panels rendering */}
        {(() => {
          return (
            <>
              {/* Onboarding Interactive Guide Modal for Guided Mode */}
              <AnimatePresence>
                {mode === 'guided' && isOpen && (
                  <InteractiveGuideModal
                    isOpen={isOpen}
                    onClose={() => setIsOpen(false)}
                    activeStep={activeStep}
                    setActiveStep={setActiveStep}
                    onLoadTemplate={handleSelectExample}
                    aiGuideData={guideData}
                    onAutoBuild={handleAutoBuild}
                  />
                )}
              </AnimatePresence>

              {/* Dynamic Level Panels rendering based on mode */}
              <AnimatePresence>
                {mode === 'guided' && guideData && !isOpen && (
                  <BuildGuidePanel
                    validationState={currentValidationState}
                    onAutoBuild={handleAutoBuild}
                    onReset={handleReset}
                  />
                )}
              </AnimatePresence>

              {/* AI Instructions Guide Generation Loader Overlay */}
              <AnimatePresence>
                {aiLoading && (
                  <motion.div
                    initial={{ opacity: 0, y: 20, scale: 0.95 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: -20, scale: 0.95 }}
                    transition={{ duration: 0.3 }}
                    style={{
                      position: 'absolute',
                      right: 20,
                      top: 20,
                      zIndex: 400,
                      width: 320,
                      background: 'rgba(15, 23, 42, 0.85)',
                      backdropFilter: 'blur(12px)',
                      border: '1px solid rgba(168, 85, 247, 0.3)',
                      borderRadius: 16,
                      padding: 16,
                      boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.5), 0 0 15px rgba(168, 85, 247, 0.15)',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 12
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <div style={{
                        width: 28,
                        height: 28,
                        borderRadius: '50%',
                        background: 'rgba(168, 85, 247, 0.15)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: '#c084fc'
                      }}>
                        <Sparkles size={14} className="animate-pulse" />
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column' }}>
                        <span style={{ fontSize: 13, fontWeight: 700, color: '#f8fafc' }}>AI Guide Builder</span>
                        <span style={{ fontSize: 10, color: '#c084fc', fontWeight: 500 }}>Formulating your simulation guide</span>
                      </div>
                    </div>
                    
                    <p style={{ fontSize: 11, color: '#cbd5e1', margin: 0, lineHeight: 1.4 }}>
                      Analyzing physics concepts and mapping interactive steps for the sandbox...
                    </p>

                    <div style={{ width: '100%', backgroundColor: 'rgba(255, 255, 255, 0.05)', border: '1px solid rgba(168, 85, 247, 0.1)', height: 6, borderRadius: 3, overflow: 'hidden', position: 'relative' }}>
                      <motion.div
                        style={{
                          height: '100%',
                          background: 'linear-gradient(90deg, #a855f7, #ec4899)',
                          borderRadius: 3,
                          width: '40%',
                          position: 'absolute',
                        }}
                        animate={{
                          left: ['-40%', '100%']
                        }}
                        transition={{
                          repeat: Infinity,
                          duration: 1.8,
                          ease: 'easeInOut'
                        }}
                      />
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </>
          );
        })()}
      </div>

      {/* ── Right panel ─────────────────────────────────────── */}
      <aside
        style={{
          ...S.rightSidebar,
          position: isMobile ? 'absolute' : 'relative',
          right: 0,
          top: 0,
          zIndex: isMobile ? 300 : 'auto',
          width: rightPanelOpen ? 320 : 0,
          minWidth: rightPanelOpen ? 300 : 0,
          padding: rightPanelOpen ? '20px 16px' : 0,
          borderLeft: rightPanelOpen ? S.rightSidebar.borderLeft : 'none',
          opacity: rightPanelOpen ? 1 : 0,
          transition: 'all 0.35s cubic-bezier(0.4, 0, 0.2, 1)',
          overflowY: rightPanelOpen ? 'auto' : 'hidden',
          overflowX: 'hidden',
        }}
      >
        {propertyControllerRef.current && storeRef.current && (
          <PropertyPanel
            store={storeRef.current}
            propertyController={propertyControllerRef.current}
            observableEngine={observableEngineRef.current}
          />
        )}
      </aside>

      {/* ── Drag ghost (follows cursor globally) ──────────── */}
      {isDragging && (
        <div
          style={{
            position: 'fixed',
            left: ghostPos.x,
            top: ghostPos.y,
            transform: 'translate(-50%, -50%)',
            width: ['pivot', 'spring', 'rope'].includes(panelDragRef.current || '') ? 48
              : panelDragRef.current === 'pendulum-rope' ? 52
                : panelDragRef.current === 'sun' ? 70
                  : panelDragRef.current === 'planet' ? 32
                    : (panelDragRef.current === 'circle' ? 44 : 40),
            height: ['pivot', 'spring', 'rope'].includes(panelDragRef.current || '') ? 48
              : panelDragRef.current === 'pendulum-rope' ? 52
                : panelDragRef.current === 'sun' ? 70
                  : panelDragRef.current === 'planet' ? 32
                    : (panelDragRef.current === 'circle' ? 44 : 40),
            borderRadius: panelDragRef.current === 'circle' || panelDragRef.current === 'pivot' || panelDragRef.current === 'sun' || panelDragRef.current === 'planet' ? '50%'
              : panelDragRef.current === 'pendulum-rope' ? 12
                : 10,
            background: panelDragRef.current === 'circle'
              ? 'rgba(16,185,129,0.55)'
              : panelDragRef.current === 'rectangle'
                ? 'rgba(99,102,241,0.55)'
                : panelDragRef.current === 'pendulum-rope'
                  ? 'rgba(99,102,241,0.45)'
                  : panelDragRef.current === 'pivot'
                    ? 'rgba(139,92,246,0.55)'
                    : panelDragRef.current === 'spring'
                      ? 'rgba(16,185,129,0.55)'
                      : panelDragRef.current === 'sun'
                        ? 'rgba(234,179,8,0.7)'
                        : panelDragRef.current === 'planet'
                          ? 'rgba(14,165,233,0.7)'
                          : 'rgba(251,191,36,0.55)',
            border: `2px solid ${panelDragRef.current === 'pendulum-rope' ? '#818cf8' :
              panelDragRef.current === 'circle' || panelDragRef.current === 'spring' ? '#6ee7b7' :
                panelDragRef.current === 'rectangle' ? '#a5b4fc' :
                  panelDragRef.current === 'pivot' ? '#c084fc' :
                    panelDragRef.current === 'sun' ? '#f97316' :
                      panelDragRef.current === 'planet' ? '#38bdf8' : '#fde047'
              }`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 18,
            color: '#fff',
            backdropFilter: 'blur(6px)',
            pointerEvents: 'none',
            zIndex: 9999,
            transition: 'opacity 0.1s',
            boxShadow: isOverCanvas
              ? '0 0 0 6px rgba(99,102,241,0.25), 0 8px 24px rgba(0,0,0,0.4)'
              : '0 4px 16px rgba(0,0,0,0.35)',
          }}
        >
          {panelDragRef.current === 'pivot' && '📌'}
          {panelDragRef.current === 'spring' && '🌀'}
          {panelDragRef.current === 'rope' && '🔗'}
          {panelDragRef.current === 'pendulum-rope' && '🪢'}
          {panelDragRef.current === 'sun' && '☀️'}
          {panelDragRef.current === 'planet' && '🌎'}
        </div>
      )}

    </div>
  );
};

const formatScientific = (val: number, unit: string) => {
  if (isNaN(val) || !isFinite(val)) return `0.00 ${unit}`;
  const absVal = Math.abs(val);
  if (absVal === 0) return `0.00 ${unit}`;

  if (absVal >= 1000 || absVal < 0.01) {
    const exp = val.toExponential(2);
    const [base, power] = exp.split('e');
    const superscriptMap: Record<string, string> = {
      '-': '⁻', '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴', '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹'
    };
    const formattedPower = power
      .replace('+', '')
      .split('')
      .map(c => superscriptMap[c] || c)
      .join('');
    return `${base} × 10${formattedPower} ${unit}`;
  }
  return `${val.toFixed(2)} ${unit}`;
};

const formatTime = (timeMs: number) => {
  const totalSecs = Math.floor(timeMs / 1000);
  const secs = totalSecs % 60;
  const mins = Math.floor(totalSecs / 60) % 60;
  const hrs = Math.floor(totalSecs / 3600);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(hrs)}:${pad(mins)}:${pad(secs)}`;
};

const Sep: React.FC<{ label: string }> = ({ label }) => (
  <div style={{
    margin: '14px 0 10px', fontSize: 9, fontWeight: 700,
    letterSpacing: '0.12em', color: '#334155', textTransform: 'uppercase' as const,
    borderBottom: '1px solid #1e293b', paddingBottom: 4
  }}>{label}</div>
);

// ─── Styles ───────────────────────────────────────────────────────────────────

const S: Record<string, React.CSSProperties> = {
  root: {
    display: 'flex', width: '100%', height: '100%', minHeight: 560,
    background: '#ffffff', color: '#1e293b',
    fontFamily: '"Plus Jakarta Sans",system-ui,sans-serif',
    overflow: 'hidden', userSelect: 'none', position: 'relative'
  },
  panel: {
    width: 288, minWidth: 268, height: '100%', padding: '20px 16px',
    background: '#ffffff', backdropFilter: 'blur(20px)',
    borderRight: '2px solid #f1f5f9',
    display: 'flex', flexDirection: 'column', overflowY: 'auto',
    flexShrink: 0
  },
  rightSidebar: {
    width: 320, minWidth: 300, height: '100%', background: '#ffffff',
    backdropFilter: 'blur(20px)', borderLeft: '2px solid #f1f5f9',
    display: 'flex', flexDirection: 'column', overflowY: 'auto',
    flexShrink: 0
  },
  header: { display: 'flex', alignItems: 'center', gap: 7, marginBottom: 4 },
  pulse: {
    width: 10, height: 10, borderRadius: '50%', background: '#4F8EF7',
    boxShadow: '0 0 0 3px rgba(79,142,247,0.28)', flexShrink: 0
  },
  tag: {
    fontSize: 11, fontWeight: 700, letterSpacing: '0.12em',
    color: '#4F8EF7', textTransform: 'uppercase'
  },
  title: {
    fontSize: 22, fontWeight: 800, margin: '2px 0 2px', letterSpacing: '-0.03em',
    color: '#0f172a'
  },
  subtitle: { fontSize: 13, color: '#64748b', marginBottom: 16 },
  cards: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 8 },
  card: {
    background: '#f8fafc', border: '2px solid #e2e8f0',
    borderRadius: 12, padding: '10px 12px', transition: 'border-color 0.2s'
  },
  cardLbl: {
    fontSize: 11, fontWeight: 700, letterSpacing: '0.05em',
    color: '#64748b', textTransform: 'uppercase', marginBottom: 4
  },
  cardVal: {
    fontSize: 14, fontWeight: 700, color: '#0f172a',
    display: 'flex', alignItems: 'center', gap: 5
  },
  dot: { display: 'inline-block', width: 8, height: 8, borderRadius: '50%', flexShrink: 0 },
  row: { display: 'flex', gap: 8, marginBottom: 8 },
  btn: {
    padding: '8px 14px', borderRadius: 10, border: '1px solid transparent',
    cursor: 'pointer', fontSize: 13, fontWeight: 700,
    transition: 'opacity 0.15s, transform 0.1s', outline: 'none'
  },
  btnPrimary: { background: '#4F8EF7', color: '#fff', borderColor: '#3b82f6' },
  btnGhost: { background: '#f1f5f9', color: '#475569', borderColor: '#e2e8f0' },
  btnIndigo: { background: '#eff6ff', color: '#4F8EF7', borderColor: '#bfdbfe' },
  btnEmerald: { background: '#f0fdf4', color: '#22C55E', borderColor: '#bbf7d0' },
  btnSky: { background: '#fff7ed', color: '#F97316', borderColor: '#ffedd5' },
  gravRow: {
    display: 'flex', gap: 4, background: '#f1f5f9',
    borderRadius: 12, padding: 4, border: '1px solid #e2e8f0', marginBottom: 16
  },
  gravBtn: {
    flex: 1, padding: '6px 0', background: 'transparent', border: 'none',
    borderRadius: 8, cursor: 'pointer', fontSize: 11, fontWeight: 700,
    color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.06em', transition: 'all 0.15s'
  },
  gravActive: { background: '#4F8EF7', color: '#fff' },
  hint: {
    fontSize: 11, color: '#64748b', lineHeight: 1.55, marginTop: 'auto', paddingTop: 14,
    borderTop: '1px solid #f1f5f9'
  },
  canvasWrap: { flex: 1, position: 'relative', overflow: 'hidden', background: '#ffffff', cursor: 'default', transition: 'outline 0.15s' },
  dropHint: {
    position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)',
    padding: '8px 18px', borderRadius: 12, background: 'rgba(79,142,247,0.15)',
    border: '2px dashed #4F8EF7', color: '#4F8EF7', fontSize: 14,
    fontWeight: 700, pointerEvents: 'none', backdropFilter: 'blur(8px)'
  },
  dotGrid: {
    position: 'absolute', inset: 0, pointerEvents: 'none',
    backgroundImage: 'radial-gradient(#e2e8f0 1.5px,transparent 1.5px)',
    backgroundSize: '20px 20px', opacity: 0.8
  },
  mount: { position: 'absolute', inset: 0 },
  badge: {
    position: 'absolute', bottom: 124, right: 14, display: 'flex', alignItems: 'center',
    padding: '5px 12px', borderRadius: 8, backdropFilter: 'blur(12px)',
    background: 'rgba(15,23,42,0.8)', border: '1px solid rgba(255,255,255,0.08)',
    fontSize: 11, color: '#818cf8', pointerEvents: 'none'
  },

  // Property Editor Panel Styles
  editorContainer: {
    background: 'rgba(255, 255, 255, 0.02)',
    border: '1px solid rgba(255, 255, 255, 0.06)',
    borderRadius: 12,
    padding: '10px 12px',
    marginBottom: 8,
    display: 'flex',
    flexDirection: 'column',
    gap: 10,
  },
  editorHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
    paddingBottom: 4,
  },
  editorTitle: {
    fontSize: 12,
    fontWeight: 700,
    color: '#a5b4fc',
  },
  deselectBtn: {
    background: 'transparent',
    border: 'none',
    color: '#64748b',
    cursor: 'pointer',
    fontSize: 12,
    padding: 0,
    lineHeight: '1',
  },
  editorSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: 6,
  },
  sectionLabel: {
    fontSize: 8,
    fontWeight: 700,
    color: '#64748b',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.08em',
  },
  controlRow: {
    display: 'flex',
    flexDirection: 'column',
    gap: 3,
  },
  toggleRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 2,
  },
  toggleBtn: {
    padding: '4px 8px',
    borderRadius: 6,
    border: '1px solid',
    cursor: 'pointer',
    fontSize: 9,
    fontWeight: 600,
    transition: 'all 0.15s',
  },
  controlLabel: {
    fontSize: 9,
    color: '#94a3b8',
  },
  sliderContainer: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  slider: {
    flex: 1,
    accentColor: '#6366f1',
    cursor: 'pointer',
    height: 4,
  },
  controlVal: {
    fontSize: 9,
    color: '#818cf8',
    minWidth: 32,
    textAlign: 'right' as const,
    fontFamily: 'monospace',
  },
  colorPalette: {
    display: 'flex',
    gap: 4,
    flexWrap: 'wrap',
    marginTop: 2,
  },
  telemetryGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: 4,
    background: 'rgba(0, 0, 0, 0.25)',
    borderRadius: 8,
    padding: 6,
    border: '1px solid rgba(255, 255, 255, 0.03)',
  },
  telemetryItem: {
    display: 'flex',
    flexDirection: 'column',
  },
  telemetryLabel: {
    fontSize: 7,
    color: '#475569',
    textTransform: 'uppercase' as const,
  },
  telemetryVal: {
    fontSize: 9,
    color: '#94a3b8',
    fontFamily: 'monospace',
  },
  noSelectionCard: {
    padding: '10px',
    borderRadius: 8,
    border: '1px dashed rgba(255, 255, 255, 0.08)',
    textAlign: 'center' as const,
    background: 'rgba(255, 255, 255, 0.01)',
  },
  constraintsList: {
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
    maxHeight: 180,
    overflowY: 'auto' as const,
    paddingRight: 4,
    marginBottom: 8,
  },
  constraintCard: {
    background: 'rgba(255, 255, 255, 0.02)',
    border: '1px solid rgba(255, 255, 255, 0.05)',
    borderRadius: 8,
    padding: 6,
    display: 'flex',
    flexDirection: 'column',
    gap: 4,
  },
  constraintCardHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderBottom: '1px solid rgba(255, 255, 255, 0.03)',
    paddingBottom: 2,
  },
  constraintName: {
    fontSize: 9,
    fontWeight: 600,
    color: '#cbd5e1',
  },
  floatingHud: {
    position: 'absolute',
    top: 14,
    right: 14,
    width: 260,
    background: 'rgba(15, 23, 42, 0.88)',
    backdropFilter: 'blur(20px)',
    border: '1px solid rgba(255, 255, 255, 0.08)',
    borderRadius: 12,
    padding: 12,
    boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4), inset 0 1px 1px rgba(255, 255, 255, 0.05)',
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
    pointerEvents: 'none',
    zIndex: 100,
  },
  floatingHudTitle: {
    fontSize: 9,
    fontWeight: 800,
    color: '#818cf8',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.08em',
    borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
    paddingBottom: 4,
  },
  floatingHudEq: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'rgba(0, 0, 0, 0.3)',
    borderRadius: 8,
    padding: '8px 10px',
    textAlign: 'center' as const,
  },
  floatingHudGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr 1.2fr',
    gap: 6,
  },
  floatingHudCard: {
    display: 'flex',
    flexDirection: 'column',
    background: 'rgba(255, 255, 255, 0.02)',
    border: '1px solid rgba(255, 255, 255, 0.04)',
    borderRadius: 6,
    padding: '5px 6px',
    textAlign: 'center' as const,
  },
  floatingHudLabel: {
    fontSize: 7,
    color: '#64748b',
    fontWeight: 700,
    textTransform: 'uppercase' as const,
    marginBottom: 2,
  },
  floatingHudValue: {
    fontSize: 9,
    fontWeight: 700,
    fontFamily: 'monospace',
  },
};

export default SandboxCanvas;
