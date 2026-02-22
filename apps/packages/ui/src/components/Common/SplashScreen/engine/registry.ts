import type { EffectLoader, SplashEffect } from "./types";

/**
 * Lazy-loading effect registry.
 * Each effect is a separate chunk — only the selected effect loads at runtime.
 * Keys match the `effect` field in card_definitions / splash-cards.ts.
 */
const EFFECTS: Record<string, EffectLoader> = {
  // Classic (16)
  matrix_rain: () => import("../effects/classic/MatrixRain"),
  glitch_reveal: () => import("../effects/classic/GlitchReveal"),
  typewriter: () => import("../effects/classic/Typewriter"),
  fade: () => import("../effects/classic/Fade"),
  pulse: () => import("../effects/classic/Pulse"),
  glitch: () => import("../effects/classic/Glitch"),
  blink: () => import("../effects/classic/Blink"),
  retro_terminal: () => import("../effects/classic/RetroTerminal"),
  pixel_dissolve: () => import("../effects/classic/PixelDissolve"),
  loading_bar: () => import("../effects/classic/LoadingBar"),
  scrolling_credits: () => import("../effects/classic/ScrollingCredits"),
  old_film: () => import("../effects/classic/OldFilm"),
  pixel_zoom: () => import("../effects/classic/PixelZoom"),
  ascii_morph: () => import("../effects/classic/AsciiMorph"),
  text_explosion: () => import("../effects/classic/TextExplosion"),
  spotlight: () => import("../effects/classic/Spotlight"),

  // Tech (23)
  fractal_zoom: () => import("../effects/tech/FractalZoom"),
  data_stream: () => import("../effects/tech/DataStream"),
  binary_matrix: () => import("../effects/tech/BinaryMatrix"),
  dna_sequence: () => import("../effects/tech/DnaSequence"),
  ascii_spinner: () => import("../effects/tech/AsciiSpinner"),
  code_scroll: () => import("../effects/tech/CodeScroll"),
  typewriter_news: () => import("../effects/tech/TypewriterNews"),
  neural_network: () => import("../effects/tech/NeuralNetwork"),
  phonebooths_dialing: () => import("../effects/tech/PhoneboothsDialing"),
  spy_vs_spy: () => import("../effects/tech/SpyVsSpy"),
  digital_rain: () => import("../effects/tech/DigitalRain"),
  cyberpunk_glitch: () => import("../effects/tech/CyberpunkGlitch"),
  chaotic_typewriter: () => import("../effects/tech/ChaoticTypewriter"),
  quantum_tunnel: () => import("../effects/tech/QuantumTunnel"),
  rubiks_cube: () => import("../effects/tech/RubiksCube"),
  hacker_terminal: () => import("../effects/tech/HackerTerminal"),
  circuit_trace: () => import("../effects/tech/CircuitTrace"),
  music_visualizer: () => import("../effects/tech/MusicVisualizer"),
  circuit_board: () => import("../effects/tech/CircuitBoard"),
  holographic_interface: () => import("../effects/tech/HolographicInterface"),
  terminal_boot: () => import("../effects/tech/TerminalBoot"),
  mining: () => import("../effects/tech/Mining"),
  neon_sign_flicker: () => import("../effects/tech/NeonSignFlicker"),

  // Environmental (23)
  doom_fire: () => import("../effects/environmental/DoomFire"),
  ascii_wave: () => import("../effects/environmental/AsciiWave"),
  plasma_field: () => import("../effects/environmental/PlasmaField"),
  ascii_fire: () => import("../effects/environmental/AsciiFire"),
  quantum_particles: () => import("../effects/environmental/QuantumParticles"),
  starfield: () => import("../effects/environmental/Starfield"),
  ascii_kaleidoscope: () => import("../effects/environmental/AsciiKaleidoscope"),
  spiral_galaxy: () => import("../effects/environmental/SpiralGalaxy"),
  morphing_shape: () => import("../effects/environmental/MorphingShape"),
  dna_helix: () => import("../effects/environmental/DnaHelix"),
  raindrops: () => import("../effects/environmental/Raindrops"),
  wave_ripple: () => import("../effects/environmental/WaveRipple"),
  train_journey: () => import("../effects/environmental/TrainJourney"),
  clock_mechanism: () => import("../effects/environmental/ClockMechanism"),
  ascii_aquarium: () => import("../effects/environmental/AsciiAquarium"),
  constellation_map: () => import("../effects/environmental/ConstellationMap"),
  bookshelf_browser: () => import("../effects/environmental/BookshelfBrowser"),
  particle_swarm: () => import("../effects/environmental/ParticleSwarm"),
  fireworks: () => import("../effects/environmental/Fireworks"),
  origami_folding: () => import("../effects/environmental/OrigamiFolding"),
  ant_colony: () => import("../effects/environmental/AntColony"),
  weather_system: () => import("../effects/environmental/WeatherSystem"),
  zen_garden: () => import("../effects/environmental/ZenGarden"),

  // Gaming (13)
  retro_gaming_intro: () => import("../effects/gaming/RetroGamingIntro"),
  world_map: () => import("../effects/gaming/WorldMap"),
  character_select: () => import("../effects/gaming/CharacterSelect"),
  pacman: () => import("../effects/gaming/Pacman"),
  achievement_unlocked: () => import("../effects/gaming/AchievementUnlocked"),
  tetris: () => import("../effects/gaming/Tetris"),
  level_up: () => import("../effects/gaming/LevelUp"),
  versus_screen: () => import("../effects/gaming/VersusScreen"),
  space_invaders: () => import("../effects/gaming/SpaceInvaders"),
  tetris_block: () => import("../effects/gaming/TetrisBlock"),
  sound_bars: () => import("../effects/gaming/SoundBars"),
  game_of_life: () => import("../effects/gaming/GameOfLife"),
  maze_generator: () => import("../effects/gaming/MazeGenerator"),

  // Psychedelic (10)
  melting_screen: () => import("../effects/psychedelic/MeltingScreen"),
  deep_dream: () => import("../effects/psychedelic/DeepDream"),
  hypno_swirl: () => import("../effects/psychedelic/HypnoSwirl"),
  trippy_tunnel: () => import("../effects/psychedelic/TrippyTunnel"),
  shroom_vision: () => import("../effects/psychedelic/ShroomVision"),
  electric_sheep: () => import("../effects/psychedelic/ElectricSheep"),
  psychedelic_mandala: () => import("../effects/psychedelic/PsychedelicMandala"),
  kaleidoscope: () => import("../effects/psychedelic/Kaleidoscope"),
  lava_lamp: () => import("../effects/psychedelic/LavaLamp"),
  ascii_mandala: () => import("../effects/psychedelic/AsciiMandala"),

  // Custom (2)
  emoji_face: () => import("../effects/custom/EmojiFace"),
  custom_image: () => import("../effects/custom/CustomImage"),
};

/** Load an effect by name. Returns null if the effect doesn't exist. */
export async function loadEffect(name: string): Promise<SplashEffect | null> {
  const loader = EFFECTS[name];
  if (!loader) {
    console.warn(`[SplashScreen] Unknown effect: "${name}"`);
    return null;
  }
  try {
    const mod = await loader();
    return new mod.default();
  } catch (err) {
    console.error(`[SplashScreen] Failed to load effect "${name}":`, err);
    return null;
  }
}

/** Get all registered effect names. */
export function listEffects(): string[] {
  return Object.keys(EFFECTS);
}
