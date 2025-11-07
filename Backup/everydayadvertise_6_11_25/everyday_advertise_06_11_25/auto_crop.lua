-- MPV Lua script for automatic cropping based on video width
-- Crops 5760px-wide videos to show middle 1920px slice (screen 2)
-- Leaves other resolutions untouched

local screen_num = tonumber(mp.get_opt("screen-num")) or 2
local slice_width = 1920
local target_video_width = 5760

function on_video_params_change()
    local width = mp.get_property_number("width")
    local height = mp.get_property_number("height")
    
    if not width or not height then
        return
    end
    
    mp.msg.info(string.format("Video loaded: %dx%d", width, height))
    
    -- Only crop 5760-wide videos (slice videos for 3-screen setup)
    if width == target_video_width then
        local x_offset = (screen_num - 1) * slice_width
        local crop_filter = string.format("lavfi=[crop=%d:%d:%d:0]", slice_width, height, x_offset)
        mp.set_property("vf", crop_filter)
        mp.msg.info(string.format("Applied crop: %s (slice video detected)", crop_filter))
    else
        -- Clear any crop filter for non-slice content
        mp.set_property("vf", "")
        mp.msg.info(string.format("No crop applied (non-slice content: %dx%d)", width, height))
    end
end

-- Watch for video parameter changes
mp.observe_property("width", "number", on_video_params_change)
mp.observe_property("height", "number", on_video_params_change)

mp.msg.info("Auto-crop script loaded for screen " .. screen_num)
