"use strict";
const {entrypoints}=require("uxp"),{Panel}=require("./ui/panel.js"),{InfoStylingApp}=require("./app.js");
const panel=new Panel(),app=new InfoStylingApp(panel);
entrypoints.setup({panels:{infostylingPanel:{show(){panel.bind({capacity:app.capacity,decode:app.decode,paired:app.paired,loadFile:app.loadFile,saveFile:app.saveFile,oneClick:app.oneClick,previews:app.previews})}}}});
