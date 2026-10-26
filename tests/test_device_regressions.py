"""LuaJIT regressions for issues observed during PW5 device acceptance."""
from pathlib import Path
from lupa.luajit21 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]

def runtime():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.globals().plugin_root = ROOT.as_posix()
    lua.execute(r'''
package.path=plugin_root..'/?.lua;'..package.path
saved,notices,physical={},{},{}
for i=1,31 do physical[i]={fp=string.format('/books/book%02d.epub',i),mtime=i,size=10} end
package.loaded['infra/sui_store']={get=function(_,k) return saved[k] end,
 readSetting=function(_,k) return saved[k] end,set=function(_,k,v) saved[k]=v end,
 saveSetting=function(_,k,v) saved[k]=v end,nilOrTrue=function(_,k) return saved[k]~=false end}
package.loaded['infra/sui_i18n']={translate=function(s) return s end}
package.loaded['infra/sui_config']={readChoice=function(k,options,default) return saved[k] or default end}
package.loaded['infra/sui_core']={PAD=0,Notify={toast=function(text) notices[#notices+1]=text end}}
package.loaded['features/sui_label_style']={}
package.loaded['engines/sui_page_nav']={}
for _,name in ipairs({'ui/widget/container/centercontainer','ui/widget/container/framecontainer',
 'ui/geometry','ui/widget/horizontalgroup','ui/widget/horizontalspan','ui/widget/container/leftcontainer'}) do
 package.loaded[name]={}
end
package.loaded['libs/libkoreader-lfs']={attributes=function() return 'file' end}
package.loaded['modules/module_books_shared']={getBookData=function(fp) return {title=fp} end}
package.loaded['features/library/sui_finished_books']={}
package.loaded['ui/uimanager']={nextTick=function(_,fn) fn() end}
package.loaded['engines/sui_screen_engine']={markAllStale=function() end,
 liveScreenIds=function() return {} end,refreshAllLiveImmediate=function() end}
-- build() memoizes the list per ctx like GridRenderer.build does
package.loaded['engines/sui_book_grid']={makeModule=function(spec)
 spec.build=function(_,ctx) ctx._row_fps_flat_library=ctx._row_fps_flat_library or spec.getFileList(ctx); return ctx._row_fps_flat_library end
 return spec end,getBookTitle=function(fp) return fp end}
Hidden=require('features/library/sui_hidden_books')
PageState=require('engines/sui_section_label').PageState
''')
    scan = (ROOT / 'engines/sui_library_scan.lua').read_text(encoding='utf-8')
    raw = scan[scan.index('function LibraryScan.getRaw('):scan.index('--- Convenience wrapper')]
    lua.execute('local LibraryScan={}\nlocal function getEntry() return {list=physical} end\n' + raw +
                "\nLibraryScan.resolveHomeDir=function() return '/books' end\nLibraryScan.invalidate=function() end\nLibraryScan.getBatchTextMeta=function() return {} end\npackage.loaded['engines/sui_library_scan']=LibraryScan")
    lua.execute("Library=require('modules/module_library')")
    return lua

def page_survives_rebuild_and_visibility():
    runtime().execute(r'''
local ctx={pfx='simpleui_hs_'}
assert(#Library.getFileList(ctx)==31)
PageState.setPage(ctx,'flat_library',4)
Hidden.hide('/books/book01.epub')
local rebuilt={pfx='simpleui_hs_'}
assert(#Library.getFileList(rebuilt)==30)
assert(PageState.get(rebuilt,'flat_library')==4,'hide/context rebuild lost page 4')
Hidden.restore('/books/book01.epub')
assert(#Library.getFileList(rebuilt)==31)
assert(PageState.get(rebuilt,'flat_library')==4,'restoring an existing book was treated as a new arrival')
local other={pfx='custom_screen_'}
assert(PageState.get(other,'flat_library')==1,'screen page state leaked between screens')
''')

def genuine_arrivals_and_sort_choice():
    runtime().execute(r'''
local ctx={pfx='simpleui_hs_'}
Library.getFileList(ctx);PageState.setPage(ctx,'flat_library',3)
physical[#physical+1]={fp='/books/new.epub',mtime=100,size=10}
local fps=Library.getFileList(ctx)
assert(fps[1]=='/books/new.epub' and PageState.get(ctx,'flat_library')==1)
saved.simpleui_hs_flat_library_sort_mode='title_asc'
PageState.setPage(ctx,'flat_library',2)
physical[#physical+1]={fp='/books/another.epub',mtime=101,size=10}
Library.getFileList(ctx)
assert(PageState.get(ctx,'flat_library')==2,'arrival overwrote the user title-sort page')
''')

def arrival_resets_kept_alive_screen():
    runtime().execute(r'''
local ctx={pfx='simpleui_hs_'}
Library.build(nil,ctx);PageState.setPage(ctx,'flat_library',2)
physical[#physical+1]={fp='/books/book32.epub',mtime=200,size=10}
local fps=Library.build(nil,ctx)
assert(fps[1]=='/books/book32.epub' and PageState.get(ctx,'flat_library')==1,'book received on a kept-alive home screen did not return to page 1')
PageState.setPage(ctx,'flat_library',3)
Library.build(nil,ctx)
assert(PageState.get(ctx,'flat_library')==3,'rebuilding an unchanged library reset the page')
saved.simpleui_hs_flat_library_sort_mode='title_asc'
physical[#physical+1]={fp='/books/book33.epub',mtime=201,size=10}
fps=Library.build(nil,ctx)
assert(fps[1]=='/books/book01.epub' and PageState.get(ctx,'flat_library')==3,'cached-grid arrival overwrote title sorting or its page')
''')

def deleting_last_page_clamps_to_previous():
    lua=runtime()
    source=(ROOT/'engines/sui_book_grid.lua').read_text(encoding='utf-8')
    body=source[source.index('local function _resolveCurrentPage('):source.index('function GridRenderer.build(')]
    resolve=lua.execute(body+'\nreturn _resolveCurrentPage')
    lua.globals().resolve=resolve
    lua.execute(r'''
local ctx={pfx='clamp_test_'};PageState.setPage(ctx,'flat_library',5)
local files={};for i=1,32 do files[i]='book'..i end
local page,count=resolve(files,ctx,'flat_library',8,true,true)
assert(page==4 and count==4,'removed final-page item jumped to page 1 instead of last valid page')
''')

def restoring_shows_confirmation():
    runtime().execute(r'''
Hidden.hide('/books/book01.epub')
local rows=Hidden.makeMenuItem().sub_item_table_func()
rows[1].sub_item_table[1].callback()
assert(not Hidden.isHidden('/books/book01.epub'))
assert(#notices==1 and notices[1]:find('book01.epub',1,true),'restore saved silently without visible feedback')
''')

def onboarding_can_build_preset_picker():
    runtime().execute(r'''
package.loaded['logger']={}
package.loaded['util']={tableDeepCopy=function(value) return value end}
package.loaded['engines/sui_window']={ListRow=function(opts) return opts end,
 SectionLabel=function(opts) return opts end}
local Presets=require('features/sui_presets')
local selected
local rows=Presets.buildListRows{
 inner_w=600,is_checked=function(id) return id=='builtin_at_a_glance' end,
 on_builtin=function(preset) selected=preset.id end}
assert(#rows>0 and rows[1].radio and rows[1].checked,'welcome picker did not build selectable presets')
rows[1].on_tap()
assert(selected=='builtin_at_a_glance','welcome picker did not dispatch preset selection')
''')

failures=0
for test in (page_survives_rebuild_and_visibility, genuine_arrivals_and_sort_choice,
             arrival_resets_kept_alive_screen,
             deleting_last_page_clamps_to_previous, restoring_shows_confirmation,
             onboarding_can_build_preset_picker):
    try:
        test()
        print('PASS',test.__name__)
    except Exception as error:
        failures+=1
        print('FAIL',test.__name__,str(error).splitlines()[0])

lua=LuaRuntime(unpack_returned_tuples=True)
for rel in ('features/sui_presets.lua','features/library/sui_hidden_books.lua','engines/sui_section_label.lua',
            'engines/sui_library_scan.lua','engines/sui_book_grid.lua','modules/module_library.lua'):
    result=lua.eval('function(path) local f,e=loadfile(path); return f~=nil,e end')(str(ROOT/rel))
    if not result[0]:
        failures+=1
        print('FAIL LuaJIT syntax',rel,result[1])
print('LuaJIT regression failures:',failures)
raise SystemExit(bool(failures))
