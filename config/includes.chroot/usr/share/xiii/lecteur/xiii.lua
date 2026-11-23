-- OS XIII — XIII Lecteur : timecode (celui de la caméra si le fichier en a un), scopes (forme d'onde, vecteurscope, histogramme),
-- zébras, aide à l'écran. Application développée par Matthieu Lamotte.
local opts = { tc = true }
local scope = nil
local debut_tc = nil

local function fps()
  local f = mp.get_property_number("container-fps") or mp.get_property_number("estimated-vf-fps") or 25
  if f <= 0 then f = 25 end
  return f
end

local function tc_en_images(s, f)
  local h, m, sec, img = s:match("(%d+)[:;](%d+)[:;](%d+)[:;.](%d+)")
  if not h then return nil end
  return ((tonumber(h) * 60 + tonumber(m)) * 60 + tonumber(sec)) * math.floor(f + 0.5) + tonumber(img)
end

local function images_en_tc(n, f)
  local r = math.floor(f + 0.5)
  local img = n % r; local s = math.floor(n / r)
  return string.format("%02d:%02d:%02d:%02d", math.floor(s / 3600) % 24, math.floor(s / 60) % 60, s % 60, img)
end

local function lire_tc_depart()
  debut_tc = nil
  local meta = mp.get_property_native("metadata") or {}
  for k, v in pairs(meta) do
    if k:lower() == "timecode" then debut_tc = v end
  end
  if not debut_tc then
    local tr = mp.get_property_native("track-list") or {}
    for _, t in ipairs(tr) do
      if t["metadata"] and t["metadata"]["timecode"] then debut_tc = t["metadata"]["timecode"] end
    end
  end
  if not debut_tc then   -- dernier recours : ffprobe (timecode dans le flux vidéo ou la piste tmcd)
    local p = mp.get_property("path")
    if p and not p:match("^%a+://") then
      local r = mp.command_native({ name = "subprocess", capture_stdout = true, playback_only = false,
        args = { "ffprobe", "-v", "error", "-show_entries", "format_tags=timecode:stream_tags=timecode", "-of", "default=nw=1:nk=1", p } })
      if r and r.stdout then debut_tc = r.stdout:match("(%d+[:;]%d+[:;]%d+[:;.]%d+)") end
    end
  end
end

local function afficher()
  if not opts.tc then mp.set_osd_ass(0, 0, ""); return end
  local f = fps(); local pos = mp.get_property_number("time-pos") or 0
  local n = math.floor(pos * f + 0.0001)
  local base = debut_tc and tc_en_images(debut_tc, f) or 0
  local txt = images_en_tc(base + n, f)
  local a, b = mp.get_property_number("ab-loop-a"), mp.get_property_number("ab-loop-b")
  local boucle = ""
  if a and b then boucle = string.format("   ⟲ A %s → B %s", images_en_tc(base + math.floor(a * f), f), images_en_tc(base + math.floor(b * f), f))
  elseif a then boucle = "   ⟲ A posé (l pour B)" end
  local source = debut_tc and "TC caméra" or "TC fichier"
  local w, h = mp.get_osd_size()
  mp.set_osd_ass(w, h, string.format("{\\an7\\pos(24,22)\\fnIBM Plex Mono\\fs34\\bord2\\3c&H12161A&\\1c&H78B3F0&}%s{\\fs20\\1c&HE3E9EE&}   %s · %.3g i/s · image %d%s",
    txt, source, f, n, boucle))
end

local function scope_filtre(k)
  if k == "waveform" then return "lavfi=[split[m][s];[s]scale=-2:360,format=yuv444p,waveform=g=green:fl=numbers:i=0.04,scale=480:200,format=yuv420p[w];[m][w]overlay=W-w-20:H-h-20]" end
  if k == "vectorscope" then return "lavfi=[split[m][s];[s]scale=-2:360,format=yuv444p,vectorscope=m=color3:g=color:i=0.06,scale=260:260,format=yuv420p[v];[m][v]overlay=W-w-20:H-h-20]" end
  if k == "histogramme" then return "lavfi=[split[m][s];[s]scale=-2:360,format=yuv444p,histogram=display_mode=overlay:level_height=160,scale=420:180,format=yuv420p[g];[m][g]overlay=W-w-20:H-h-20]" end
  if k == "zebra" then return "lavfi=[split[m][z];[z]lutyuv=y='if(gte(val\\,235)\\,255\\,0)':u=128:v=128,format=gray[zz];[m][zz]blend=all_mode=screen:all_opacity=0.5]" end
end

local function basculer(k, nom)
  mp.command("vf remove @xiiiscope")
  if scope == k then scope = nil; mp.osd_message(nom .. " masqué", 1); return end
  scope = k
  local ok = mp.commandv("vf", "add", "@xiiiscope:" .. scope_filtre(k))
  mp.osd_message(ok and (nom .. " (même touche pour masquer)") or (nom .. " indisponible pour ce fichier"), 2)
end

mp.add_key_binding(nil, "waveform", function() basculer("waveform", "Forme d'onde") end)
mp.add_key_binding(nil, "vectorscope", function() basculer("vectorscope", "Vecteurscope") end)
mp.add_key_binding(nil, "histogramme", function() basculer("histogramme", "Histogramme") end)
mp.add_key_binding(nil, "zebra", function() basculer("zebra", "Zébras (hautes lumières)") end)
mp.add_key_binding(nil, "timecode", function() opts.tc = not opts.tc; afficher() end)
mp.add_key_binding(nil, "aide", function()
  mp.osd_message("XIII Lecteur\n\nEspace : lecture / pause    . et , : image suivante / précédente\n← → : 1 s    Maj + ← → : 10 s    [ ] : vitesse\n" ..
    "l : boucle A puis B (3e appui : efface)    L : répéter le fichier\nw : forme d'onde    v : vecteurscope    h : histogramme    z : zébras\n" ..
    "t : timecode    s : sous-titres    a : piste son    p : capture de l'image\ni : infos techniques    f : plein écran    q : quitter", 8)
end)

mp.register_event("file-loaded", function() lire_tc_depart(); afficher() end)
mp.observe_property("time-pos", "number", afficher)
mp.observe_property("ab-loop-a", "native", afficher)
mp.observe_property("ab-loop-b", "native", afficher)
mp.observe_property("osd-dimensions", "native", afficher)
