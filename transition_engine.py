import pygame, logging, os, math
from typing import Optional

logger = logging.getLogger(__name__)

class TransitionEngine:
    def __init__(self, screen):
        self.screen = screen
        self.width, self.height = screen.get_size()
        self.clock = pygame.time.Clock()
        try:
            self.duration = float(os.getenv("PHTV_TRANSITION_SEC", "0.6"))
        except:
            self.duration = 0.5
        try:
            self.fps = int(os.getenv("PHTV_TRANSITION_FPS", "24"))
        except:
            self.fps = 30
        # Offscreen render scale for performance (0.4 - 1.0)
        try:
            scale = float(os.getenv("PHTV_TRANSITION_SCALE", "0.5"))
        except:
            scale = 0.6
        self.scale = max(0.4, min(1.0, scale))
        self.test_flash_enabled = os.getenv("PHTV_TEST_FLASH", "0").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )

    # Offscreen helpers
    def _offscreen_size(self):
        if self.scale >= 0.999:
            return self.width, self.height
        return max(1, int(self.width * self.scale)), max(1, int(self.height * self.scale))

    def _new_offscreen(self) -> pygame.Surface:
        w, h = self._offscreen_size()
        return pygame.Surface((w, h), flags=pygame.SRCALPHA).convert_alpha()

    # Helpers for smoother, time-based animations
    def _ease(self, t: float) -> float:
        """Smoothstep easing for less choppy motion."""
        t = max(0.0, min(1.0, t))
        return t * t * (3 - 2 * t)

    def _prep_surface(self, surface: Optional[pygame.Surface]) -> Optional[pygame.Surface]:
        if not surface:
            return None
        try:
            if surface.get_size() != (self.width, self.height):
                surface = pygame.transform.scale(surface, (self.width, self.height))
            # convert_alpha matches display format for faster blits with alpha
            return surface.convert_alpha()
        except Exception:
            return surface

    def _downscale(self, surface: Optional[pygame.Surface]) -> Optional[pygame.Surface]:
        if not surface:
            return None
        try:
            w, h = self._offscreen_size()
            if (w, h) != surface.get_size():
                surface = pygame.transform.scale(surface, (w, h))
            return surface.convert_alpha()
        except Exception:
            return surface

    def _present(self, offscreen: pygame.Surface):
        if self.scale >= 0.999:
            # Offscreen is full-res; draw directly
            self.screen.blit(offscreen, (0, 0))
        else:
            try:
                # Optional smoother upscale (slower). Enable via PHTV_TRANSITION_SMOOTH_UPSCALE=1
                if os.getenv("PHTV_TRANSITION_SMOOTH_UPSCALE", "0").strip() in ("1","true","yes","on"):
                    scaled = pygame.transform.smoothscale(offscreen, (self.width, self.height))
                else:
                    scaled = pygame.transform.scale(offscreen, (self.width, self.height))
            except Exception:
                scaled = offscreen
            self.screen.blit(scaled, (0, 0))

    def _animate(self, render_fn, fps: Optional[int] = None):
        """Run a time-based animation for self.duration seconds at ~fps (default self.fps).
        render_fn receives (offscreen_surface, t) with t in [0,1]."""
        duration_ms = max(1, int(self.duration * 1000))
        start = pygame.time.get_ticks()
        off = self._new_offscreen()
        target_fps = int(fps or self.fps)
        while True:
            now = pygame.time.get_ticks()
            elapsed = now - start
            t = min(1.0, elapsed / duration_ms)
            # Keep the OS event queue from freezing (esp. under X11/VNC)
            try:
                pygame.event.pump()
            except Exception:
                pass
            try:
                render_fn(off, t)
                self._present(off)
                pygame.display.flip()
            except Exception:
                # Best-effort: continue frames even if one blit fails
                pass
            if t >= 1.0:
                break
            # Pace to target FPS
            self.clock.tick(target_fps)

    def apply_transition(self, from_surface, to_surface, effect):
        if not to_surface:
            return False
        if to_surface.get_size() != (self.width, self.height):
            to_surface = pygame.transform.scale(to_surface, (self.width, self.height))
        
        if self.test_flash_enabled:
            try:
                import time as _debug_t

                logger.info(f"🎬 TRANSITION START: Showing bright test pattern for {effect}")
                for color, name in [((0, 255, 0), "GREEN"), ((0, 0, 255), "BLUE"), ((255, 255, 0), "YELLOW")]:
                    try:
                        self.screen.fill(color)
                        pygame.display.flip()
                        logger.info(f"   ⚡ Flashing {name}")
                        _debug_t.sleep(0.3)
                    except Exception as flip_err:
                        logger.warning(f"   ⚠️  Flash {name} failed: {flip_err}, continuing anyway...")
                        break
            except Exception as e:
                logger.warning(f"   ⚠️  Test pattern partially failed: {e}, continuing with transition...")
        
        try:
            e = effect.lower().strip() if effect else "cut"
            if e in ("cut", "none", ""): self._cut(to_surface)
            elif e == "fade": self._fade(from_surface, to_surface)
            elif e == "dissolve": self._dissolve(from_surface, to_surface)
            elif e == "slide_left": self._slide_left(from_surface, to_surface)
            elif e == "slide_right": self._slide_right(from_surface, to_surface)
            elif e == "slide_up": self._slide_up(from_surface, to_surface)
            elif e == "slide_down": self._slide_down(from_surface, to_surface)
            elif e == "zoom_in": self._zoom_in(from_surface, to_surface)
            elif e == "zoom_out": self._zoom_out(from_surface, to_surface)
            elif e == "wipe": self._wipe(from_surface, to_surface)
            else: self._cut(to_surface)
            return True
        except Exception as ex:
            logger.error(str(ex))
            try:
                self.screen.fill((0, 0, 0))
                self.screen.blit(to_surface, (0, 0))
                pygame.display.flip()
            except:
                pass
            return True

    def _cut(self, to_surface):
        self.screen.fill((0, 0, 0))
        self.screen.blit(to_surface, (0, 0))
        try:
            pygame.display.flip()
        except:
            pass

    def _fade(self, from_surface, to_surface):
        from_scaled = self._prep_surface(from_surface)
        to_scaled = self._prep_surface(to_surface)
        from_small = self._downscale(from_scaled) if from_scaled else None
        to_small = self._downscale(to_scaled)

        def render(off, t: float):
            off.fill((0, 0, 0, 255))
            if from_small:
                if t < 0.5:
                    a = self._ease(t * 2.0)
                    from_small.set_alpha(int(255 * (1.0 - a)))
                    off.blit(from_small, (0, 0))
            if t >= 0.5 and to_small:
                a = self._ease((t - 0.5) * 2.0)
                to_small.set_alpha(int(255 * a))
                off.blit(to_small, (0, 0))

        self._animate(render)
        # Final frame: ensure destination fully visible
        self.screen.fill((0, 0, 0))
        self.screen.blit(to_surface, (0, 0))
        try:
            pygame.display.flip()
        except:
            pass

    def _dissolve(self, from_surface, to_surface):
        from_scaled = self._prep_surface(from_surface)
        to_scaled = self._prep_surface(to_surface)
        from_small = self._downscale(from_scaled) if from_scaled else None
        to_small = self._downscale(to_scaled)

        def render(off, t: float):
            a = self._ease(t)
            off.fill((0, 0, 0, 255))
            if from_small:
                from_small.set_alpha(int(255 * (1.0 - a)))
                off.blit(from_small, (0, 0))
            if to_small:
                to_small.set_alpha(int(255 * a))
                off.blit(to_small, (0, 0))

        self._animate(render)
        self.screen.fill((0, 0, 0))
        self.screen.blit(to_surface, (0, 0))
        try:
            pygame.display.flip()
        except:
            pass

    def _slide_left(self, from_surface, to_surface):
        bg = self._downscale(self._prep_surface(from_surface)) if from_surface else None
        to_small = self._downscale(self._prep_surface(to_surface))
        off_w, off_h = self._offscreen_size()

        def render(off, t: float):
            e = self._ease(t)
            x_offset = int(off_w * (1.0 - e))
            off.fill((0, 0, 0, 255))
            if bg:
                off.blit(bg, (0, 0))
            if to_small:
                off.blit(to_small, (x_offset, 0))

        self._animate(render)
        self.screen.fill((0, 0, 0))
        self.screen.blit(to_surface, (0, 0))
        try:
            pygame.display.flip()
        except:
            pass

    def _slide_right(self, from_surface, to_surface):
        bg = self._downscale(self._prep_surface(from_surface)) if from_surface else None
        to_small = self._downscale(self._prep_surface(to_surface))
        off_w, off_h = self._offscreen_size()

        def render(off, t: float):
            e = self._ease(t)
            x_offset = int(-off_w * (1.0 - e))
            off.fill((0, 0, 0, 255))
            if bg:
                off.blit(bg, (0, 0))
            if to_small:
                off.blit(to_small, (x_offset, 0))

        self._animate(render)
        self.screen.fill((0, 0, 0))
        self.screen.blit(to_surface, (0, 0))
        try:
            pygame.display.flip()
        except:
            pass

    def _slide_up(self, from_surface, to_surface):
        bg = self._downscale(self._prep_surface(from_surface)) if from_surface else None
        to_small = self._downscale(self._prep_surface(to_surface))
        off_w, off_h = self._offscreen_size()

        def render(off, t: float):
            e = self._ease(t)
            y_offset = int(off_h * (1.0 - e))
            off.fill((0, 0, 0, 255))
            if bg:
                off.blit(bg, (0, 0))
            if to_small:
                off.blit(to_small, (0, y_offset))

        self._animate(render)
        self.screen.fill((0, 0, 0))
        self.screen.blit(to_surface, (0, 0))
        try:
            pygame.display.flip()
        except:
            pass

    def _slide_down(self, from_surface, to_surface):
        bg = self._downscale(self._prep_surface(from_surface)) if from_surface else None
        to_small = self._downscale(self._prep_surface(to_surface))
        off_w, off_h = self._offscreen_size()

        def render(off, t: float):
            e = self._ease(t)
            y_offset = int(-off_h * (1.0 - e))
            off.fill((0, 0, 0, 255))
            if bg:
                off.blit(bg, (0, 0))
            if to_small:
                off.blit(to_small, (0, y_offset))

        self._animate(render)
        self.screen.fill((0, 0, 0))
        self.screen.blit(to_surface, (0, 0))
        try:
            pygame.display.flip()
        except:
            pass

    def _zoom_in(self, from_surface, to_surface):
        # New: crossfade from old to new while new zooms in from 80% -> 100%
        from_small = self._downscale(self._prep_surface(from_surface)) if from_surface else None
        to_small_full = self._downscale(self._prep_surface(to_surface))
        off_w, off_h = self._offscreen_size()

        def render(off, t: float):
            e = self._ease(t)
            off.fill((0, 0, 0, 255))
            # Fade out old
            if from_small:
                a_from = int(255 * (1.0 - e))
                from_small.set_alpha(a_from)
                off.blit(from_small, (0, 0))
            # Zoom in new
            scale = 0.8 + 0.2 * e
            w = max(1, int(off_w * scale))
            h = max(1, int(off_h * scale))
            x = (off_w - w) // 2
            y = (off_h - h) // 2
            try:
                scaled = pygame.transform.scale(to_small_full, (w, h))
            except Exception:
                scaled = to_small_full
            if scaled:
                # Fade in new slightly to mask aliasing at start
                a_to = int(200 + 55 * e)
                try:
                    scaled.set_alpha(a_to)
                except Exception:
                    pass
                off.blit(scaled, (x, y))

        # Cap zoom transitions at 24 FPS for performance
        self._animate(render, fps=min(self.fps, 24))
        # Final frame
        self.screen.fill((0, 0, 0))
        self.screen.blit(to_surface, (0, 0))
        try:
            pygame.display.flip()
        except:
            pass

    def _zoom_out(self, from_surface, to_surface):
        # New: new starts full size, zooms out to 90% while old fades out
        from_small = self._downscale(self._prep_surface(from_surface)) if from_surface else None
        to_small_full = self._downscale(self._prep_surface(to_surface))
        off_w, off_h = self._offscreen_size()

        def render(off, t: float):
            e = self._ease(t)
            off.fill((0, 0, 0, 255))
            # Fade out old
            if from_small:
                a_from = int(255 * (1.0 - e))
                from_small.set_alpha(a_from)
                off.blit(from_small, (0, 0))
            # Zoom out new
            scale = 1.0 - 0.1 * e
            w = max(1, int(off_w * scale))
            h = max(1, int(off_h * scale))
            x = (off_w - w) // 2
            y = (off_h - h) // 2
            try:
                scaled = pygame.transform.scale(to_small_full, (w, h))
            except Exception:
                scaled = to_small_full
            if scaled:
                a_to = int(220 + 35 * e)
                try:
                    scaled.set_alpha(a_to)
                except Exception:
                    pass
                off.blit(scaled, (x, y))

        self._animate(render, fps=min(self.fps, 24))
        self.screen.fill((0, 0, 0))
        self.screen.blit(to_surface, (0, 0))
        try:
            pygame.display.flip()
        except:
            pass

    def _wipe(self, from_surface, to_surface):
        # Wipe with soft edge to reduce harshness
        bg = self._downscale(self._prep_surface(from_surface)) if from_surface else None
        to_small = self._downscale(self._prep_surface(to_surface))
        off_w, off_h = self._offscreen_size()
        feather = max(2, int(off_w * 0.02))  # ~2% soft edge

        def render(off, t: float):
            e = self._ease(t)
            wipe_width = int(off_w * e)
            off.fill((0, 0, 0, 255))
            if bg:
                off.blit(bg, (0, 0))
            if to_small and wipe_width > 0:
                # Main reveal area
                area = pygame.Rect(0, 0, min(max(0, wipe_width - feather), off_w), off_h)
                if area.width > 0:
                    off.blit(to_small, (0, 0), area=area)
                # Feathered edge
                edge_w = min(feather, max(0, wipe_width - area.width))
                if edge_w > 0:
                    edge_area = pygame.Rect(area.width, 0, edge_w, off_h)
                    slice_surf = to_small.subsurface(edge_area).copy()
                    # Alpha gradient across feather width
                    alpha = int(255 * (edge_w / max(1, feather)))
                    slice_surf.set_alpha(alpha)
                    off.blit(slice_surf, (area.width, 0))

        self._animate(render)
        self.screen.fill((0, 0, 0))
        self.screen.blit(to_surface, (0, 0))
        try:
            pygame.display.flip()
        except:
            pass

    def capture_screen(self):
        """Capture current screen content as a surface for next transition"""
        try:
            return self.screen.copy()
        except Exception as e:
            logger.error(f"Failed to capture screen: {e}")
            return None
