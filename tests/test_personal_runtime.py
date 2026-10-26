"""Refresh ownership, version ordering, updater selection and translation checks."""
from pathlib import Path
from lupa.lua54 import LuaRuntime
import polib
ROOT=Path(__file__).resolve().parents[1]
lua=LuaRuntime(unpack_returned_tuples=True)
lua.globals().plugin_root=ROOT.as_posix()
lua.execute(r'''
package.path=plugin_root.."/?.lua;"..package.path
local saved={}
package.loaded["infra/sui_store"]={get=function(_,k) return saved[k] end,
set=function(_,k,v) saved[k]=v end,nilOrTrue=function(_,k) return saved[k]~=false end}
package.loaded["infra/sui_i18n"]={translate=function(s) return s end}
local ticks={}
local scans,stale,repaints,fc_refresh=0,0,0,0
local live=true
local chooser={refreshPath=function() fc_refresh=fc_refresh+1 end}
local fm={file_chooser=chooser}
package.loaded["apps/filemanager/filemanager"]={instance=fm}
package.loaded["engines/sui_library_scan"]={invalidate=function() scans=scans+1 end}
package.loaded["engines/sui_screen_engine"]={markAllStale=function() stale=stale+1 end,
liveScreenIds=function() return live and {"hs"} or {} end,
refreshAllLiveImmediate=function() repaints=repaints+1 end}
package.loaded["ui/uimanager"]={nextTick=function(_,fn) ticks[#ticks+1]=fn end}
local Hidden=require("features/library/sui_hidden_books")
local closed=0
Hidden.refresh(function() closed=closed+1 end)
assert(scans==1 and stale==1 and closed==1 and #ticks==0 and fc_refresh==0)
Hidden.refresh();ticks[1]()
assert(repaints==1 and fc_refresh==0,"home refresh must have one owner")
live=false;Hidden.refresh();ticks[2]()
assert(fc_refresh==1 and fm._navbar_suppress_path_change==nil)
fm._navbar_suppress_path_change="existing"
chooser.refreshPath=function() error("paint failed") end
Hidden.refresh();assert(not pcall(ticks[3]))
assert(fm._navbar_suppress_path_change=="existing")
local row
Hidden.registerHoldAction({addFileDialogButtons=function(_,id,f) row=f end})
saved.simpleui_enabled=false
assert(row("/book.epub",true)==nil)
saved.simpleui_enabled=nil
assert(row("/book.epub",true)[1].callback)
local V=require("infra/sui_version")
assert(V.greater("v3.0.0-personal.11","3.0.0-personal.2"))
assert(not V.greater("3.0.0-personal.2","3.0.0-personal.11"))
assert(not V.greater("3.0.0-personal.1","3.0.0-personal.1"))
assert(V.greater("3.0.1-personal.1","3.0.0-personal.99"))
assert(V.greater("3.0.0","3.0.0-personal.11"))
assert(not V.greater("3.0.0-personal.11","3.0.0"))
assert(not V.greater("broken","3.0.0"))
''')
lua.execute(r'''
local shown,persisted={},{}
local asset="https://github.com/dhhp2k1/simpleui.koplugin/releases/download/"
local function release(tag,url)
 return {tag_name=tag,prerelease=true,body="Notes",assets={{name="simpleui.koplugin.zip",
 browser_download_url=url or asset..tag.."/simpleui.koplugin.zip"}}}
end
local releases={release("v3.0.0-personal.2"),release("v3.0.0-personal.11"),
release("v99.0.0-personal.1","https://github.com/other/repo/releases/download/x/simpleui.koplugin.zip"),
{tag_name="v99.0.0-personal.2",draft=true,assets={}}}
package.loaded["json"]={decode=function() return releases end}
package.loaded["ui/uimanager"]={show=function(_,o) shown[#shown+1]=o end,
close=function() end,scheduleIn=function(_,_,fn) fn() end}
package.loaded["features/dialogs/sui_dialogs"]={confirm=function(o) shown[#shown+1]=o end}
package.loaded["logger"]={info=function() end,warn=function() end,err=function() end}
package.loaded["util"]={trim=function(s) return s end}
package.loaded["infra/sui_core"]={Notify={toast=function() return {} end}}
package.loaded["infra/sui_text"]={truncate=function(s) return s end}
package.loaded["infra/sui_paths"]={getPluginDirNoSlash=function() return plugin_root end}
package.loaded["socket"]={skip=function(n,...) return select(n+1,...) end}
package.loaded["ltn12"]={sink={table=function(chunks)
 return function(s) if s then chunks[#chunks+1]=s end;return 1 end end}}
package.loaded["socket/http"]={request=function(req)
 assert(req.url=="https://api.github.com/repos/dhhp2k1/simpleui.koplugin/releases?per_page=20")
 req.sink("fixture");return 1,200,{} end}
G_reader_settings={readSetting=function(_,k) return persisted[k] end,
saveSetting=function(_,k,v) persisted[k]=v end}
local Updater=require("infra/sui_updater")
Updater._doManualCheck("3.0.0-personal.1")
assert(#shown==1 and shown[1].text:find("3.0.0-personal.11",1,true))
assert(Updater.hasUpdate())
assert(persisted.simpleui_personal_upd_dl_url==asset.."v3.0.0-personal.11/simpleui.koplugin.zip")
''')
for name in ("simpleui.pot","zh_CN.po","zh_TW.po"):
    polib.pofile(str(ROOT/"locale"/name),check_for_duplicates=True).to_binary()
print("PASS: refresh ownership, exception cleanup, disabled-plugin gate, version ordering, personal release selection and Chinese PO syntax.")
