    def _get_crop_filter_for_url(self, url):
        """Extract crop parameters from slice URL or screen ID for horizontal split."""
        try:
            screen_id = getattr(self, 'screen_id', '1') or '1'
            
            # Parse slice parameters from URL if present
            if 'slice_mode=split-h' in url and 'slice_count=3' in url:
                # Horizontal 3-way split for screens 1, 2, 3
                if 'slice_order=0' in url or screen_id == '1':
                    # Screen 1 (left third): crop right 2/3
                    return {"top": 0, "bottom": 0, "left": 0, "right": 2}
                elif 'slice_order=1' in url or screen_id == '2':
                    # Screen 2 (middle third): crop left 1/3 and right 1/3
                    return {"top": 0, "bottom": 0, "left": 1, "right": 1}
                elif 'slice_order=2' in url or screen_id == '3':
                    # Screen 3 (right third): crop left 2/3
                    return {"top": 0, "bottom": 0, "left": 2, "right": 0}
            
            # For screens 2 and 3 without explicit slice URL, apply default 3-way horizontal crop
            elif screen_id == '2':
                return {"top": 0, "bottom": 0, "left": 1, "right": 1}
            elif screen_id == '3':
                return {"top": 0, "bottom": 0, "left": 2, "right": 0}
            
        except Exception as e:
            print(f"⚠️ Error parsing crop filter: {e}")
        
        return None