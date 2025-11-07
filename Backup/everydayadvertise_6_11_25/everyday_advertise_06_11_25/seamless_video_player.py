#!/usr/bin/env python3
"""
Seamless Video Player using python-mpv bindings
NO FLICKER - videos transition smoothly using internal playlist
"""

import os
import collections
import hashlib
import subprocess
import mpv
import pygame
import threading
import time
import logging
from pathlib import Path
from typing import Optional, Callable
from transition_engine import TransitionEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SeamlessVideoPlayer:
    """Custom video player with zero-flicker transitions"""
    
    def __init__(self, window_size=(2560, 1440), screen=None):
        self.window_size = window_size
        self.player: Optional[mpv.MPV] = None
        self.current_video: Optional[str] = None
        self.next_video: Optional[str] = None
        self.is_playing = False
        self.playback_lock = threading.Lock()
        self.on_video_end: Optional[Callable] = None
        self.display_rotation = 0
        
        # Use existing pygame screen if provided (don't create a new one)
        if screen:
            self.screen = screen
        else:
            # Only create pygame window if not provided
            if not os.environ.get("SDL_VIDEODRIVER"):
                os.environ["SDL_VIDEODRIVER"] = "x11"
            os.environ.setdefault("SDL_RENDER_DRIVER", "software")
            os.environ.setdefault("SDL_VIDEO_X11_NODIRECTCOLOR", "1")
            os.environ.setdefault("SDL_VIDEO_CENTERED", "1")
            pygame.init()
            self.screen = pygame.display.set_mode(window_size, pygame.FULLSCREEN | pygame.SWSURFACE, 32)
            pygame.display.set_caption("Pizza Hut TV")
            pygame.mouse.set_visible(False)
        
        # Determine native window id for embedding MPV into the same window (avoids stacking/flicker)
        self._window_id = None
        try:
            wm_info = pygame.display.get_wm_info()
            # On X11, key is 'window'; on Windows it's 'window', on Wayland embedding may not be supported
            self._window_id = wm_info.get('window')
            logger.info(f"🪟 Embed target window id: {self._window_id}")
        except Exception as e:
            logger.warning(f"⚠️  Could not get window id for embedding: {e}")

        self._init_player()
        
    def _init_player(self):
        """Initialize MPV player with optimal settings"""
        try:
            # Build MPV with embedding into the pygame window to prevent black flashes from window stacking
            mpv_kwargs = dict(
                # Video output (use GPU with OpenGL on X11 for smooth vsync)
                vo='gpu',

                # Hardware decoding - explicit copy-back path for X11 on Raspberry Pi
                # This avoids slow-motion from software decode and works under X11 compositors
                hwdec='v4l2m2m-copy',
                hwdec_codecs='h264,hevc,mpeg2video',
                
                # Window settings - embed into our window instead of a separate fullscreen window
                # MPV will render inside the SDL window; pygame controls the top-level surface.
                # This removes WM stacking races that cause black flicker on the Pi.
                fullscreen=False,
                ontop=False,
                border=False,
                autofit=f'{self.window_size[0]}x{self.window_size[1]}',
                
                # No UI elements
                osc=False,
                osd_level=0,
                cursor_autohide='always',
                
                # Audio
                audio='auto',
                volume=100,
                
                # Performance
                profile='gpu-hq',
                # Prefer stable timing without frame blending to avoid "slow motion" feel
                video_sync='audio',
                interpolation=False,
                # Ensure playback speed is normal
                speed=1.0,
                framedrop='vo',
                vd_lavc_threads=2,
                # Prefer lightweight scaling for low-power GPUs
                scale='bilinear',
                dscale='bilinear',
                
                # Keep window open between videos
                keep_open='always',
                idle='yes',

                # Reduce gaps at item boundaries
                prefetch_playlist=True,
                cache='yes',
                cache_secs='5',
                
                # Video scaling to fill screen
                keepaspect=True,
                
                # Logging
                msg_level='all=info',
            )

            if self._window_id:
                mpv_kwargs['wid'] = int(self._window_id)

            self.player = mpv.MPV(**mpv_kwargs)
            
            # Register event handlers
            @self.player.event_callback('end-file')
            def on_end_file(event):
                logger.info(f"🎬 Video ended: {event}")
                if self.on_video_end:
                    self.on_video_end()
            
            # Pending seek target for sync-aligned starts
            self._pending_seek_sec = None

            @self.player.event_callback('file-loaded')
            def on_file_loaded(event):
                # Log display and content FPS to diagnose smoothness
                try:
                    disp_fps = self.player.get_property('display-fps')
                except Exception:
                    disp_fps = None
                try:
                    cont_fps = self.player.get_property('container-fps')
                except Exception:
                    cont_fps = None
                try:
                    est_fps = self.player.get_property('estimated-vf-fps')
                except Exception:
                    est_fps = None
                logger.info(
                    f"✅ Video loaded | display-fps={disp_fps} | container-fps={cont_fps} | estimated-fps={est_fps}"
                )
                # Apply pending seek if requested (for cross-device sync alignment)
                try:
                    if self._pending_seek_sec is not None and self._pending_seek_sec >= 0:
                        tgt = float(self._pending_seek_sec)
                        try:
                            # Use absolute, exact seek to minimize phase error
                            self.player.command('seek', tgt, 'absolute', 'exact')
                        except Exception:
                            try:
                                self.player.seek(tgt)
                            except Exception:
                                pass
                finally:
                    self._pending_seek_sec = None
                self.is_playing = True
            
            logger.info("✅ MPV player initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize MPV player: {e}")
            raise

    def set_display_rotation(self, angle: int):
        """Update the preferred display rotation for MPV playback."""
        try:
            angle = int(angle) % 360
        except Exception:
            angle = 0

        if angle not in (0, 90, 180, 270):
            angle = (round(angle / 90) * 90) % 360

        if angle == self.display_rotation:
            return

        self.display_rotation = angle
        if not self.player:
            return

        applied = False
        try:
            self.player.set_property('video-rotate', angle)
            applied = True
        except Exception:
            try:
                self.player['video_rotate'] = angle
                applied = True
            except Exception:
                pass

        if not applied:
            try:
                self.player.command('set', 'video-rotate', str(angle))
                applied = True
            except Exception as mpv_err:
                logger.warning(f"⚠️  Unable to update MPV rotation: {mpv_err}")

        if applied:
            logger.info(f"↻ MPV rotation set to {angle}°")
    
    def play_video(self, video_path: str, duration: Optional[float] = None, start_position: Optional[float] = None):
        """
        Play a video with seamless transition
        
        Args:
            video_path: Path to video file
            duration: Optional duration limit in seconds
            start_position: Optional start position in seconds for sync alignment
        """
        with self.playback_lock:
            try:
                if not Path(video_path).exists():
                    logger.error(f"❌ Video file not found: {video_path}")
                    return False
                
                logger.info(f"▶️  Playing video: {video_path}")
                
                # If already playing, this creates seamless transition
                # Record pending seek before starting playback; will be applied on file-loaded
                try:
                    self._pending_seek_sec = float(start_position) if start_position is not None else None
                except Exception:
                    self._pending_seek_sec = None

                if self.is_playing and self.player:
                    logger.info("🔄 Seamless transition to next video...")
                    # Re-enable video output and unpause if needed
                    try:
                        self.player['vid'] = 'auto'  # Restore video rendering
                        if self.player.pause:
                            self.player.pause = False
                            logger.info("▶️ Unpaused MPV before playing next video")
                    except Exception as e:
                        logger.warning(f"⚠️ Could not restore MPV video: {e}")
                    # MPV internally handles smooth transition
                    self.player.play(video_path)
                else:
                    # First video
                    logger.info("🎬 Starting first video...")
                    self.player.play(video_path)
                
                # CRITICAL FIX: Enable looping to prevent black screen if video is shorter than duration
                # This matches the Android TV behavior where videos loop until the timer advances
                try:
                    self.player['loop-file'] = 'inf'  # Loop current file infinitely
                    logger.info("🔁 Enabled video looping to prevent black screen")
                except Exception as loop_err:
                    logger.warning(f"⚠️ Could not enable loop-file: {loop_err}")
                
                # NOTE: Don't try to set duration limit on MPV player
                # The Python timer in complete_pi_client.py controls when to advance to next item
                # Videos loop until timer fires (matching webplayer behavior)
                
                self.current_video = video_path
                self.is_playing = True
                
                return True
                
            except Exception as e:
                logger.error(f"❌ Error playing video: {e}")
                self.is_playing = False
                return False
    
    def queue_next_video(self, video_path: str):
        """
        Queue next video for absolutely seamless transition
        MPV will automatically start it when current finishes
        """
        try:
            if not Path(video_path).exists():
                logger.error(f"❌ Video file not found: {video_path}")
                return False
            
            logger.info(f"📋 Queuing next video: {video_path}")
            
            # Append to MPV's internal playlist
            self.player.playlist_append(video_path)
            self.next_video = video_path
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error queuing video: {e}")
            return False
    
    def show_image(self, image_surface: pygame.Surface, duration: float):
        """
        Show an image (pauses video playback)
        
        Args:
            image_surface: Pygame surface with image
            duration: How long to show image in seconds
        """
        with self.playback_lock:
            try:
                # Pause video playback
                if self.is_playing and self.player:
                    self.player.pause = True
                    logger.info("⏸️  Paused video for image display")
                
                # Display image on pygame surface
                self.screen.blit(image_surface, (0, 0))
                pygame.display.flip()
                
                # Wait for duration
                time.sleep(duration)
                
                # Resume video if was playing
                if self.is_playing and self.player:
                    self.player.pause = False
                    logger.info("▶️  Resumed video after image")
                
                return True
                
            except Exception as e:
                logger.error(f"❌ Error showing image: {e}")
                return False
    
    def pause(self):
        """Pause playback"""
        if self.player:
            self.player.pause = True
            logger.info("⏸️  Paused")
    
    def resume(self):
        """Resume playback"""
        if self.player:
            self.player.pause = False
            logger.info("▶️  Resumed")
    
    def stop(self):
        """Stop playback and show black screen"""
        with self.playback_lock:
            if self.player:
                try:
                    self.player.stop()
                    self.is_playing = False
                    self.current_video = None
                    logger.info("⏹️  Stopped")
                except:
                    pass
    
    def set_volume(self, volume: int):
        """
        Set volume (0-100)
        """
        if self.player:
            self.player.volume = max(0, min(100, volume))
            logger.info(f"🔊 Volume set to {volume}%")
    
    def get_playback_time(self) -> float:
        """Get current playback position in seconds"""
        if self.player and self.is_playing:
            try:
                return self.player.time_pos or 0.0
            except:
                return 0.0
        return 0.0
    
    def get_duration(self) -> float:
        """Get total video duration in seconds"""
        if self.player:
            try:
                return self.player.duration or 0.0
            except:
                return 0.0
        return 0.0
    
    def cleanup(self):
        """Clean up resources"""
        logger.info("🧹 Cleaning up player...")
        self.stop()
        
        if self.player:
            try:
                self.player.terminate()
            except:
                pass
        
        pygame.quit()
        logger.info("✅ Player cleaned up")


class SeamlessMediaPlayer:
    """
    Drop-in replacement for media_player.py with zero-flicker transitions
    Compatible with complete_pi_client.py interface
    """
    
    def __init__(self, screen_or_size=(2560, 1440), cache_dir="cache"):
        # Handle both pygame screen object and window_size tuple
        if isinstance(screen_or_size, tuple):
            self.window_size = screen_or_size
            self.external_screen = None
        else:
            # It's a pygame screen object
            self.external_screen = screen_or_size
            self.window_size = screen_or_size.get_size()
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # Initialize seamless video player, pass screen if we have one
        self.video_player = SeamlessVideoPlayer(self.window_size, screen=self.external_screen)
        
        # Use the video player's screen for drawing
        self.screen = self.video_player.screen
        
        # Initialize transition engine
        self.transition_engine = TransitionEngine(self.screen)

        # Image cache with LRU eviction to prevent memory growth
        self.cache_max_items = int(os.getenv("PHTV_IMAGE_CACHE_ITEMS", "60"))
        self.image_cache: collections.OrderedDict = collections.OrderedDict()

        # State
        self.is_playing = False
        self.current_media_type = None
        self.last_frame: Optional[pygame.Surface] = None  # For transitions
        self.display_rotation = 0
        self._in_transition = False
        # Video-to-video transitions: ON by default for clear visual effects.
        # Override with env:
        #   - PHTV_V2V_TRANSITIONS=0/false to turn off
        #   - PHTV_DISABLE_V2V_TRANSITIONS=1 to force off
        try:
            env_v2v = os.getenv('PHTV_V2V_TRANSITIONS')
            disable_v2v = os.getenv('PHTV_DISABLE_V2V_TRANSITIONS', '')
            if env_v2v is not None:
                self.v2v_transitions = str(env_v2v).strip().lower() in ('1','true','yes','on')
            else:
                # Default ON if not specified
                self.v2v_transitions = True
            if str(disable_v2v).strip().lower() in ('1','true','yes','on'):
                self.v2v_transitions = False
        except Exception:
            self.v2v_transitions = True
        self.video_preview_cache: collections.OrderedDict = collections.OrderedDict()
        
        logger.info("✅ Seamless Media Player initialized")

    def set_display_rotation(self, angle: int):
        """Persist and apply rotation for both images and videos."""
        try:
            angle = int(angle) % 360
        except Exception:
            angle = 0

        if angle not in (0, 90, 180, 270):
            angle = (round(angle / 90) * 90) % 360

        if angle == self.display_rotation:
            return

        logger.info(f"↻ Updating media player rotation to {angle}°")
        self.display_rotation = angle
        self.image_cache.clear()
        self.last_frame = None

        try:
            self.video_player.set_display_rotation(angle)
        except Exception as err:
            logger.warning(f"⚠️  Could not update video player rotation: {err}")
    
    def play_media(self, url: str, effect: str, duration: float, item: Optional[dict] = None, **_ignored) -> bool:
        """
        Play media with beautiful transition effects
        
        Args:
            url: URL or local path to media
            effect: Transition effect (fade, slide-l, slide-r, zoom-in, zoom-out, cut)
            duration: Duration in seconds
            item: Optional playlist item payload (used for logging/metadata)
            
        Returns:
            True if successful
        """
        try:
            if item:
                try:
                    item_id = item.get('id') if isinstance(item, dict) else getattr(item, 'id', None)
                    item_effect = item.get('effect') if isinstance(item, dict) else getattr(item, 'effect', None)
                    item_duration = item.get('duration') if isinstance(item, dict) else getattr(item, 'duration', None)
                    logger.debug(f"📝 Playlist item metadata: {item_id} effect={item_effect} duration={item_duration}")
                except Exception as meta_err:
                    logger.debug(f"📝 Playlist item metadata unavailable: {meta_err}")
            # Determine media type
            if url.endswith(('.mp4', '.webm', '.mkv', '.avi', '.mov')):
                media_type = 'video'
            else:
                media_type = 'image'
            
            logger.info(f"🎬 Playing {media_type}: {url} (effect: {effect}) for {duration}s")
            
            # Get local path (download if URL)
            if url.startswith('http'):
                local_path = self._download_media(url, media_type)
                if not local_path:
                    return False
            else:
                local_path = url
            
            if media_type == 'video' and self.current_media_type == 'video':
                if self.v2v_transitions and effect and effect.lower() != 'cut':
                    logger.info("🎬 Video-to-video transitions enabled; applying surface transition before starting next video")
                    try:
                        from_surface = self.transition_engine.capture_screen()
                    except Exception:
                        from_surface = None
                    new_surface = self._get_video_first_frame(local_path)
                    try:
                        self._in_transition = True
                        tid = self.transition_engine.begin_transition()
                        self.transition_engine.apply_transition(from_surface, new_surface, effect, tid=tid)
                    finally:
                        self._in_transition = False
                    # After transition, start the video aligned
                    start_pos = None
                    try:
                        sref = None
                        if isinstance(item, dict):
                            sref = item.get('sync_ref')
                        elif hasattr(item, 'sync_ref'):
                            sref = getattr(item, 'sync_ref', None)
                        if isinstance(sref, dict) and hasattr(self.video_player, 'time_sync') and self.video_player.time_sync:
                            server_sec = float(self.video_player.time_sync.get_server_time()) / 1000.0
                            cycle = float(duration or 0)
                            if cycle > 0:
                                if sref.get('start_epoch'):
                                    start_epoch = float(sref.get('start_epoch') or 0)
                                    start_pos = (server_sec - start_epoch) % cycle
                                else:
                                    # Fallback: align by current server-phase of duration
                                    start_pos = server_sec % cycle
                    except Exception:
                        start_pos = None
                    success = self.video_player.play_video(local_path, duration, start_position=start_pos)
                    if success:
                        self.current_media_type = 'video'
                        self.is_playing = True
                        self.last_frame = None
                    return success
                else:
                    logger.info("🎬 Video-to-video: Using MPV seamless playback (no transition needed)")
                    # Cancel any in-flight surface transitions before handing off to MPV
                    try:
                        self.transition_engine.cancel_transitions()
                    except Exception:
                        pass
                    # Ensure flag is clear in case we were transitioning
                    self._in_transition = False
                    # Compute sync-aligned start position if available
                    start_pos = None
                    try:
                        sref = None
                        if isinstance(item, dict):
                            sref = item.get('sync_ref')
                        elif hasattr(item, 'sync_ref'):
                            sref = getattr(item, 'sync_ref', None)
                        if isinstance(sref, dict) and hasattr(self.video_player, 'time_sync') and self.video_player.time_sync:
                            server_sec = float(self.video_player.time_sync.get_server_time()) / 1000.0
                            cycle = float(duration or 0)
                            if cycle > 0:
                                if sref.get('start_epoch'):
                                    start_epoch = float(sref.get('start_epoch') or 0)
                                    start_pos = (server_sec - start_epoch) % cycle
                                else:
                                    start_pos = server_sec % cycle
                    except Exception:
                        start_pos = None
                    success = self.video_player.play_video(local_path, duration, start_position=start_pos)
                    if success:
                        self.current_media_type = 'video'
                        self.is_playing = True
                        # Don't capture frame for video (MPV owns the screen)
                        self.last_frame = None
                    return success
            
            # For IMAGE or VIDEO-FROM-IMAGE: Apply transition
            # Load the new media as a surface
            if media_type == 'image':
                # If we are coming from video, hide MPV video output and grab the current frame
                from_surface = None
                if self.current_media_type == 'video':
                    try:
                        if self.video_player and self.video_player.player:
                            # Disable video rendering so pygame can show through
                            self.video_player.player['vid'] = 'no'
                            logger.info("🙈 Disabled MPV video output to show image")
                    except Exception as e:
                        logger.warning(f"⚠️  Could not disable MPV video: {e}")
                    # Capture the last presented frame from the shared SDL window
                    try:
                        from_surface = self.transition_engine.capture_screen()
                    except Exception as e:
                        logger.warning(f"⚠️  Could not capture screen for transition: {e}")

                # Load target image surface
                new_surface = self._load_image(local_path)
            else:
                # For video starting after image (or from image), use last frame placeholder
                new_surface = self._get_video_first_frame(local_path)
            
            if not new_surface:
                logger.error(f"❌ Could not load media: {local_path}")
                return False
            
            # Apply transition effect using the most accurate previous frame available
            prev_surface = None
            if media_type == 'image' and 'from_surface' in locals() and from_surface is not None:
                prev_surface = from_surface
            else:
                prev_surface = self.last_frame

            if prev_surface and effect and effect.lower() != 'cut':
                logger.info(f"🎨 Applying {effect} transition...")
                # Begin guarded transition; if a new media arrives, this animation will abort cleanly
                tid = self.transition_engine.begin_transition()
                # Signal main loop to pause background flips while we animate
                self._in_transition = True
                try:
                    self.transition_engine.apply_transition(prev_surface, new_surface, effect, tid=tid)
                finally:
                    self._in_transition = False
            else:
                # No transition - just show the new frame
                try:
                    self.screen.blit(new_surface, (0, 0))
                    pygame.display.flip()
                except pygame.error as e:
                    # GL context error - ignore and let MPV take over
                    logger.warning(f"⚠️  Pygame display error (MPV will handle display): {e}")
            
            # Now actually play the media
            if media_type == 'video':
                # Start video playback (MPV will handle the actual playback)
                # Cancel any in-flight surface transitions before starting MPV
                try:
                    self.transition_engine.cancel_transitions()
                except Exception:
                    pass
                # Ensure flag is clear in case we were transitioning
                self._in_transition = False
                # Compute sync-aligned start position if available
                start_pos = None
                try:
                    sref = None
                    if isinstance(item, dict):
                        sref = item.get('sync_ref')
                    elif hasattr(item, 'sync_ref'):
                        sref = getattr(item, 'sync_ref', None)
                    if isinstance(sref, dict) and hasattr(self.video_player, 'time_sync') and self.video_player.time_sync:
                        server_sec = float(self.video_player.time_sync.get_server_time()) / 1000.0
                        cycle = float(duration or 0)
                        if cycle > 0:
                            if sref.get('start_epoch'):
                                start_epoch = float(sref.get('start_epoch') or 0)
                                start_pos = (server_sec - start_epoch) % cycle
                            else:
                                start_pos = server_sec % cycle
                except Exception:
                    start_pos = None
                success = self.video_player.play_video(local_path, duration, start_position=start_pos)
                if success:
                    self.current_media_type = 'video'
                    self.is_playing = True
                    # Don't capture frame for video (MPV owns the screen)
                    self.last_frame = None
                return success
                
            else:  # image
                # Image is already displayed via transition
                # Capture for next transition
                self.last_frame = self.transition_engine.capture_screen()
                self.current_media_type = 'image'
                self.is_playing = True
                return True
                
        except Exception as e:
            logger.error(f"❌ Error playing media: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def queue_next(self, url: str) -> bool:
        """
        Queue next video for seamless transition
        Only works for video-to-video
        """
        try:
            if not url.endswith(('.mp4', '.webm', '.mkv', '.avi', '.mov')):
                return False  # Only queue videos
            
            # Get local path
            if url.startswith('http'):
                local_path = self._download_media(url, 'video')
                if not local_path:
                    return False
            else:
                local_path = url
            
            return self.video_player.queue_next_video(local_path)
            
        except Exception as e:
            logger.error(f"❌ Error queuing next video: {e}")
            return False
    
    def _load_image(self, image_path: str) -> Optional[pygame.Surface]:
        """Load and cache image"""
        try:
            cache_key = (image_path, self.display_rotation)
            if cache_key in self.image_cache:
                # LRU: move to end on access
                surf = self.image_cache.pop(cache_key)
                self.image_cache[cache_key] = surf
                return surf.copy()
            
            # Load and scale image
            image = pygame.image.load(image_path)
            try:
                if image.get_alpha():
                    image = image.convert_alpha()
                else:
                    image = image.convert()
            except pygame.error:
                pass

            image = self._prepare_surface_for_display(image)
            
            # Cache it with LRU eviction
            self.image_cache[cache_key] = image.copy()
            self._evict_cache_if_needed()
            return image
            
            
        except Exception as e:
            logger.error(f"❌ Error loading image: {e}")
            return None
    
    def _get_video_first_frame(self, video_path: str) -> Optional[pygame.Surface]:
        """Return a representative surface for the next video transition."""
        try:
            # Reuse cached screen capture if available
            if getattr(self, 'last_frame', None) is not None:
                try:
                    return self._prepare_surface_for_display(self.last_frame.copy())
                except Exception:
                    pass

            key = (str(video_path), self.display_rotation)
            cached = self.video_preview_cache.get(key)
            if cached is not None:
                # LRU move-to-end then return a copy for thread safety
                self.video_preview_cache.pop(key, None)
                self.video_preview_cache[key] = cached
                return cached.copy()

            vp = Path(video_path)
            if vp.exists():
                thumb_hash = hashlib.md5(str(vp).encode('utf-8')).hexdigest()
                thumb_path = self.cache_dir / f"{thumb_hash}_preview.png"

                if not thumb_path.exists():
                    cmd = [
                        'mpv',
                        '--no-config',
                        '--quiet',
                        '--frames=1',
                        '--vo=image',
                        '--image-format=png',
                        f"--image-file={thumb_path}",
                        str(vp),
                    ]
                    try:
                        subprocess.run(
                            cmd,
                            check=True,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            timeout=8,
                        )
                    except Exception as shot_err:
                        logger.debug(f"Preview capture failed ({video_path}): {shot_err}")
                        if thumb_path.exists():
                            try:
                                thumb_path.unlink(missing_ok=True)
                            except Exception:
                                pass

                if thumb_path.exists():
                    try:
                        preview = pygame.image.load(str(thumb_path))
                        preview = self._prepare_surface_for_display(preview)
                        self.video_preview_cache[key] = preview.copy()
                        self._trim_video_preview_cache()
                        return preview
                    except Exception as load_err:
                        logger.debug(f"Preview load failed ({video_path}): {load_err}")

        except Exception as e:
            logger.error(f"❌ Error getting video first frame: {e}")
            return None

        # Fallback (black frame) if no preview available
        surface = pygame.Surface(self.window_size)
        surface.fill((0, 0, 0))
        return self._prepare_surface_for_display(surface)

    def _prepare_surface_for_display(self, surface: pygame.Surface) -> pygame.Surface:
        """Scale and rotate the surface according to current display rotation."""
        angle = self.display_rotation % 360
        rotated_axis = bool(angle % 180)
        target_size = self.window_size if not rotated_axis else (self.window_size[1], self.window_size[0])

        try:
            if surface.get_size() != target_size:
                surface = pygame.transform.scale(surface, target_size)
        except Exception:
            pass

        if angle:
            try:
                surface = pygame.transform.rotate(surface, -angle)
            except Exception:
                pass

        if surface.get_size() != self.window_size:
            try:
                surface = pygame.transform.scale(surface, self.window_size)
            except Exception:
                pass

        try:
            surface = surface.convert()
        except Exception:
            pass

        return surface

    def _evict_cache_if_needed(self):
        """Evict least-recently-used cached images if over limit."""
        try:
            while len(self.image_cache) > max(1, int(self.cache_max_items)):
                # popitem(last=False) pops the oldest entry
                self.image_cache.popitem(last=False)
        except Exception:
            # If anything goes wrong, clear half the cache defensively
            try:
                keep = max(1, len(self.image_cache) // 2)
                keys = list(self.image_cache.keys())
                for k in keys[:max(0, len(keys) - keep)]:
                    self.image_cache.pop(k, None)
            except Exception:
                pass

    def _trim_video_preview_cache(self, max_items: int = 24):
        try:
            while len(self.video_preview_cache) > max_items:
                self.video_preview_cache.popitem(last=False)
        except Exception:
            try:
                self.video_preview_cache.clear()
            except Exception:
                pass
    
    def _download_media(self, url: str, media_type: str) -> Optional[str]:
        """Download media to cache"""
        try:
            import hashlib
            import requests

            # Create cache filename
            url_hash = hashlib.md5(url.encode()).hexdigest()
            ext = Path(url).suffix or ('.mp4' if media_type == 'video' else '.jpg')
            cache_path = self.cache_dir / f"{url_hash}{ext}"
            
            # Return if already cached
            if cache_path.exists():
                logger.info(f"📦 Using cached: {cache_path}")
                return str(cache_path)
            
            # Download
            logger.info(f"⬇️  Downloading: {url}")
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            with open(cache_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"✅ Downloaded: {cache_path}")
            return str(cache_path)
            
        except Exception as e:
            logger.error(f"❌ Error downloading media: {e}")
            return None
    
    def preload_media(self, url: str):
        """
        Preload media (download to cache)
        This is called by complete_pi_client to preload upcoming items
        """
        try:
            if not url or not url.startswith('http'):
                return  # Only preload remote URLs
            
            # Determine media type from URL
            if url.endswith(('.mp4', '.webm', '.mkv', '.avi', '.mov')):
                media_type = 'video'
            else:
                media_type = 'image'
            
            # Download to cache (will be used later when play_media is called)
            local_path = self._download_media(url, media_type)
            if local_path:
                logger.debug(f"📥 Preloaded: {url}")
            
        except Exception as e:
            logger.error(f"❌ Error preloading media: {e}")
    
    def stop(self):
        """Stop playback"""
        self.video_player.stop()
        self.is_playing = False
        self.current_media_type = None
    
    def pause(self):
        """Pause playback"""
        self.video_player.pause()
    
    def resume(self):
        """Resume playback"""
        self.video_player.resume()
    
    def get_cache_info(self) -> dict:
        """Get cache statistics for display"""
        import os
        
        cache_size = 0
        cache_items = 0
        
        try:
            if self.cache_dir.exists():
                for file in self.cache_dir.iterdir():
                    if file.is_file():
                        cache_size += file.stat().st_size
                        cache_items += 1
        except:
            pass
        
        return {
            'memory_items': len(self.image_cache),
            'download_items': cache_items,
            'cache_size_mb': cache_size / (1024 * 1024),
            'preload_queue': 0  # We don't have a preload queue in seamless player
        }
    
    def cleanup(self):
        """Clean up resources"""
        self.video_player.cleanup()
        self.image_cache.clear()

    def is_in_transition(self) -> bool:
        """Expose whether a transition animation is currently active."""
        return bool(self._in_transition)

    # --- Resource management helpers for long-run stability ---
    def trim_image_cache(self, max_items: int):
        """Trim the in-memory image cache to at most max_items entries."""
        try:
            self.cache_max_items = max(1, int(max_items))
            self._evict_cache_if_needed()
        except Exception:
            pass

    def enforce_download_cache_limit(self, max_mb: int):
        """Ensure on-disk download cache does not exceed max_mb by removing oldest files first."""
        try:
            max_bytes = max(0, int(max_mb)) * 1024 * 1024
            if max_bytes <= 0:
                return
            if not self.cache_dir.exists():
                return
            files = [p for p in self.cache_dir.iterdir() if p.is_file()]
            # Sort by last access time (fallback to mtime)
            files.sort(key=lambda p: (p.stat().st_atime if hasattr(p.stat(), 'st_atime') else p.stat().st_mtime))
            total = sum(p.stat().st_size for p in files)
            if total <= max_bytes:
                return
            # Remove oldest first
            for p in files:
                try:
                    size = p.stat().st_size
                    p.unlink(missing_ok=True)
                    total -= size
                    if total <= max_bytes:
                        break
                except Exception:
                    continue
        except Exception:
            pass


# Example usage
if __name__ == "__main__":
    player = SeamlessMediaPlayer()
    
    # Test with multiple videos - should have ZERO flicker
    test_videos = [
        "/path/to/video1.mp4",
        "/path/to/video2.mp4",
        "/path/to/video3.mp4",
    ]
    
    try:
        for i, video in enumerate(test_videos):
            print(f"\n🎬 Playing video {i+1}/{len(test_videos)}")
            
            # Queue next video for seamless transition
            if i < len(test_videos) - 1:
                player.queue_next(test_videos[i + 1])
            
            player.play_media(video, 'fade', 10.0)
            time.sleep(10)
        
        print("\n✅ All videos played seamlessly!")
        
    except KeyboardInterrupt:
        print("\n⏹️  Stopped by user")
    finally:
        player.cleanup()
