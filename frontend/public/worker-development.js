/*
 * ATTENTION: An "eval-source-map" devtool has been used.
 * This devtool is neither made for production nor for readable output files.
 * It uses "eval()" calls to create a separate source file with attached SourceMaps in the browser devtools.
 * If you are trying to read the output file, select a different devtool (https://webpack.js.org/configuration/devtool/)
 * or disable the default devtool with "devtool: false".
 * If you are looking for production-ready output files, see mode: "production" (https://webpack.js.org/configuration/mode/).
 */
/******/ (() => { // webpackBootstrap
/******/ 	var __webpack_modules__ = ({

/***/ "./worker/index.ts":
/*!*************************!*\
  !*** ./worker/index.ts ***!
  \*************************/
/***/ ((module, __unused_webpack_exports, __webpack_require__) => {

eval(__webpack_require__.ts("// @ts-nocheck\nself.addEventListener('push', (event)=>{\n    let data = {\n        title: \"New Notification\",\n        body: \"You have a new alert.\",\n        url: \"/\"\n    };\n    try {\n        if (event.data) {\n            data = {\n                ...data,\n                ...event.data.json()\n            };\n        }\n    } catch (e) {\n        console.error(\"Failed to parse push data\", e);\n    }\n    event.waitUntil(self.registration.showNotification(data.title, {\n        body: data.body,\n        icon: '/icon.png',\n        badge: '/icon.png',\n        data: {\n            url: data.url\n        }\n    }));\n});\nself.addEventListener('notificationclick', (event)=>{\n    event.notification.close();\n    event.waitUntil(self.clients.matchAll({\n        type: 'window'\n    }).then((clientsArr)=>{\n        const url = event.notification.data.url;\n        const hadWindowToFocus = clientsArr.some((windowClient)=>{\n            if (windowClient.url === url || windowClient.url.includes(url)) {\n                windowClient.focus();\n                return true;\n            }\n            return false;\n        });\n        if (!hadWindowToFocus && self.clients.openWindow) {\n            self.clients.openWindow(url);\n        }\n    }));\n});\n\n\n;\n    // Wrapped in an IIFE to avoid polluting the global scope\n    ;\n    (function () {\n        var _a, _b;\n        // Legacy CSS implementations will `eval` browser code in a Node.js context\n        // to extract CSS. For backwards compatibility, we need to check we're in a\n        // browser context before continuing.\n        if (typeof self !== 'undefined' &&\n            // No-JS mode does not inject these helpers:\n            '$RefreshHelpers$' in self) {\n            // @ts-ignore __webpack_module__ is global\n            var currentExports = module.exports;\n            // @ts-ignore __webpack_module__ is global\n            var prevSignature = (_b = (_a = module.hot.data) === null || _a === void 0 ? void 0 : _a.prevSignature) !== null && _b !== void 0 ? _b : null;\n            // This cannot happen in MainTemplate because the exports mismatch between\n            // templating and execution.\n            self.$RefreshHelpers$.registerExportsForReactRefresh(currentExports, module.id);\n            // A module can be accepted automatically based on its exports, e.g. when\n            // it is a Refresh Boundary.\n            if (self.$RefreshHelpers$.isReactRefreshBoundary(currentExports)) {\n                // Save the previous exports signature on update so we can compare the boundary\n                // signatures. We avoid saving exports themselves since it causes memory leaks (https://github.com/vercel/next.js/pull/53797)\n                module.hot.dispose(function (data) {\n                    data.prevSignature =\n                        self.$RefreshHelpers$.getRefreshBoundarySignature(currentExports);\n                });\n                // Unconditionally accept an update to this module, we'll check if it's\n                // still a Refresh Boundary later.\n                // @ts-ignore importMeta is replaced in the loader\n                /* unsupported import.meta.webpackHot */ undefined.accept();\n                // This field is set when the previous version of this module was a\n                // Refresh Boundary, letting us know we need to check for invalidation or\n                // enqueue an update.\n                if (prevSignature !== null) {\n                    // A boundary can become ineligible if its exports are incompatible\n                    // with the previous exports.\n                    //\n                    // For example, if you add/remove/change exports, we'll want to\n                    // re-execute the importing modules, and force those components to\n                    // re-render. Similarly, if you convert a class component to a\n                    // function, we want to invalidate the boundary.\n                    if (self.$RefreshHelpers$.shouldInvalidateReactRefreshBoundary(prevSignature, self.$RefreshHelpers$.getRefreshBoundarySignature(currentExports))) {\n                        module.hot.invalidate();\n                    }\n                    else {\n                        self.$RefreshHelpers$.scheduleUpdate();\n                    }\n                }\n            }\n            else {\n                // Since we just executed the code for the module, it's possible that the\n                // new exports made it ineligible for being a boundary.\n                // We only care about the case when we were _previously_ a boundary,\n                // because we already accepted this update (accidental side effect).\n                var isNoLongerABoundary = prevSignature !== null;\n                if (isNoLongerABoundary) {\n                    module.hot.invalidate();\n                }\n            }\n        }\n    })();\n//# sourceURL=[module]\n//# sourceMappingURL=data:application/json;charset=utf-8;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiLi93b3JrZXIvaW5kZXgudHMiLCJtYXBwaW5ncyI6IkFBQUEsY0FBYztBQUNkQSxLQUFLQyxnQkFBZ0IsQ0FBQyxRQUFRLENBQUNDO0lBQzdCLElBQUlDLE9BQU87UUFBRUMsT0FBTztRQUFvQkMsTUFBTTtRQUF5QkMsS0FBSztJQUFJO0lBQ2hGLElBQUk7UUFDRixJQUFJSixNQUFNQyxJQUFJLEVBQUU7WUFDZEEsT0FBTztnQkFBRSxHQUFHQSxJQUFJO2dCQUFFLEdBQUdELE1BQU1DLElBQUksQ0FBQ0ksSUFBSSxFQUFFO1lBQUM7UUFDekM7SUFDRixFQUFFLE9BQU9DLEdBQUc7UUFDVkMsUUFBUUMsS0FBSyxDQUFDLDZCQUE2QkY7SUFDN0M7SUFFQU4sTUFBTVMsU0FBUyxDQUNiWCxLQUFLWSxZQUFZLENBQUNDLGdCQUFnQixDQUFDVixLQUFLQyxLQUFLLEVBQUU7UUFDN0NDLE1BQU1GLEtBQUtFLElBQUk7UUFDZlMsTUFBTTtRQUNOQyxPQUFPO1FBQ1BaLE1BQU07WUFDSkcsS0FBS0gsS0FBS0csR0FBRztRQUNmO0lBQ0Y7QUFFSjtBQUVBTixLQUFLQyxnQkFBZ0IsQ0FBQyxxQkFBcUIsQ0FBQ0M7SUFDMUNBLE1BQU1jLFlBQVksQ0FBQ0MsS0FBSztJQUN4QmYsTUFBTVMsU0FBUyxDQUNiWCxLQUFLa0IsT0FBTyxDQUFDQyxRQUFRLENBQUM7UUFBRUMsTUFBTTtJQUFTLEdBQUdDLElBQUksQ0FBQyxDQUFDQztRQUM5QyxNQUFNaEIsTUFBTUosTUFBTWMsWUFBWSxDQUFDYixJQUFJLENBQUNHLEdBQUc7UUFFdkMsTUFBTWlCLG1CQUFtQkQsV0FBV0UsSUFBSSxDQUFDQyxDQUFBQTtZQUN2QyxJQUFJQSxhQUFhbkIsR0FBRyxLQUFLQSxPQUFPbUIsYUFBYW5CLEdBQUcsQ0FBQ29CLFFBQVEsQ0FBQ3BCLE1BQU07Z0JBQzlEbUIsYUFBYUUsS0FBSztnQkFDbEIsT0FBTztZQUNUO1lBQ0EsT0FBTztRQUNUO1FBRUEsSUFBSSxDQUFDSixvQkFBb0J2QixLQUFLa0IsT0FBTyxDQUFDVSxVQUFVLEVBQUU7WUFDaEQ1QixLQUFLa0IsT0FBTyxDQUFDVSxVQUFVLENBQUN0QjtRQUMxQjtJQUNGO0FBRUoiLCJzb3VyY2VzIjpbIkk6XFxQcm9qXFxUaWdhTWluZHNcXGZyb250ZW5kXFx3b3JrZXJcXGluZGV4LnRzIl0sInNvdXJjZXNDb250ZW50IjpbIi8vIEB0cy1ub2NoZWNrXG5zZWxmLmFkZEV2ZW50TGlzdGVuZXIoJ3B1c2gnLCAoZXZlbnQ6IGFueSkgPT4ge1xuICBsZXQgZGF0YSA9IHsgdGl0bGU6IFwiTmV3IE5vdGlmaWNhdGlvblwiLCBib2R5OiBcIllvdSBoYXZlIGEgbmV3IGFsZXJ0LlwiLCB1cmw6IFwiL1wiIH07XG4gIHRyeSB7XG4gICAgaWYgKGV2ZW50LmRhdGEpIHtcbiAgICAgIGRhdGEgPSB7IC4uLmRhdGEsIC4uLmV2ZW50LmRhdGEuanNvbigpIH07XG4gICAgfVxuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5lcnJvcihcIkZhaWxlZCB0byBwYXJzZSBwdXNoIGRhdGFcIiwgZSk7XG4gIH1cbiAgXG4gIGV2ZW50LndhaXRVbnRpbChcbiAgICBzZWxmLnJlZ2lzdHJhdGlvbi5zaG93Tm90aWZpY2F0aW9uKGRhdGEudGl0bGUsIHtcbiAgICAgIGJvZHk6IGRhdGEuYm9keSxcbiAgICAgIGljb246ICcvaWNvbi5wbmcnLFxuICAgICAgYmFkZ2U6ICcvaWNvbi5wbmcnLFxuICAgICAgZGF0YToge1xuICAgICAgICB1cmw6IGRhdGEudXJsXG4gICAgICB9XG4gICAgfSlcbiAgKVxufSlcblxuc2VsZi5hZGRFdmVudExpc3RlbmVyKCdub3RpZmljYXRpb25jbGljaycsIChldmVudDogYW55KSA9PiB7XG4gIGV2ZW50Lm5vdGlmaWNhdGlvbi5jbG9zZSgpXG4gIGV2ZW50LndhaXRVbnRpbChcbiAgICBzZWxmLmNsaWVudHMubWF0Y2hBbGwoeyB0eXBlOiAnd2luZG93JyB9KS50aGVuKChjbGllbnRzQXJyOiBhbnlbXSkgPT4ge1xuICAgICAgY29uc3QgdXJsID0gZXZlbnQubm90aWZpY2F0aW9uLmRhdGEudXJsXG4gICAgICBcbiAgICAgIGNvbnN0IGhhZFdpbmRvd1RvRm9jdXMgPSBjbGllbnRzQXJyLnNvbWUod2luZG93Q2xpZW50ID0+IHtcbiAgICAgICAgaWYgKHdpbmRvd0NsaWVudC51cmwgPT09IHVybCB8fCB3aW5kb3dDbGllbnQudXJsLmluY2x1ZGVzKHVybCkpIHtcbiAgICAgICAgICB3aW5kb3dDbGllbnQuZm9jdXMoKVxuICAgICAgICAgIHJldHVybiB0cnVlXG4gICAgICAgIH1cbiAgICAgICAgcmV0dXJuIGZhbHNlXG4gICAgICB9KVxuXG4gICAgICBpZiAoIWhhZFdpbmRvd1RvRm9jdXMgJiYgc2VsZi5jbGllbnRzLm9wZW5XaW5kb3cpIHtcbiAgICAgICAgc2VsZi5jbGllbnRzLm9wZW5XaW5kb3codXJsKVxuICAgICAgfVxuICAgIH0pXG4gIClcbn0pXG4iXSwibmFtZXMiOlsic2VsZiIsImFkZEV2ZW50TGlzdGVuZXIiLCJldmVudCIsImRhdGEiLCJ0aXRsZSIsImJvZHkiLCJ1cmwiLCJqc29uIiwiZSIsImNvbnNvbGUiLCJlcnJvciIsIndhaXRVbnRpbCIsInJlZ2lzdHJhdGlvbiIsInNob3dOb3RpZmljYXRpb24iLCJpY29uIiwiYmFkZ2UiLCJub3RpZmljYXRpb24iLCJjbG9zZSIsImNsaWVudHMiLCJtYXRjaEFsbCIsInR5cGUiLCJ0aGVuIiwiY2xpZW50c0FyciIsImhhZFdpbmRvd1RvRm9jdXMiLCJzb21lIiwid2luZG93Q2xpZW50IiwiaW5jbHVkZXMiLCJmb2N1cyIsIm9wZW5XaW5kb3ciXSwiaWdub3JlTGlzdCI6W10sInNvdXJjZVJvb3QiOiIifQ==\n//# sourceURL=webpack-internal:///./worker/index.ts\n"));

/***/ })

/******/ 	});
/************************************************************************/
/******/ 	// The module cache
/******/ 	var __webpack_module_cache__ = {};
/******/ 	
/******/ 	// The require function
/******/ 	function __webpack_require__(moduleId) {
/******/ 		// Check if module is in cache
/******/ 		var cachedModule = __webpack_module_cache__[moduleId];
/******/ 		if (cachedModule !== undefined) {
/******/ 			if (cachedModule.error !== undefined) throw cachedModule.error;
/******/ 			return cachedModule.exports;
/******/ 		}
/******/ 		// Create a new module (and put it into the cache)
/******/ 		var module = __webpack_module_cache__[moduleId] = {
/******/ 			id: moduleId,
/******/ 			// no module.loaded needed
/******/ 			exports: {}
/******/ 		};
/******/ 	
/******/ 		// Execute the module function
/******/ 		var threw = true;
/******/ 		try {
/******/ 			__webpack_modules__[moduleId](module, module.exports, __webpack_require__);
/******/ 			threw = false;
/******/ 		} finally {
/******/ 			if(threw) delete __webpack_module_cache__[moduleId];
/******/ 		}
/******/ 	
/******/ 		// Return the exports of the module
/******/ 		return module.exports;
/******/ 	}
/******/ 	
/************************************************************************/
/******/ 	/* webpack/runtime/trusted types policy */
/******/ 	(() => {
/******/ 		var policy;
/******/ 		__webpack_require__.tt = () => {
/******/ 			// Create Trusted Type policy if Trusted Types are available and the policy doesn't exist yet.
/******/ 			if (policy === undefined) {
/******/ 				policy = {
/******/ 					createScript: (script) => (script)
/******/ 				};
/******/ 				if (typeof trustedTypes !== "undefined" && trustedTypes.createPolicy) {
/******/ 					policy = trustedTypes.createPolicy("nextjs#bundler", policy);
/******/ 				}
/******/ 			}
/******/ 			return policy;
/******/ 		};
/******/ 	})();
/******/ 	
/******/ 	/* webpack/runtime/trusted types script */
/******/ 	(() => {
/******/ 		__webpack_require__.ts = (script) => (__webpack_require__.tt().createScript(script));
/******/ 	})();
/******/ 	
/******/ 	/* webpack/runtime/react refresh */
/******/ 	(() => {
/******/ 		if (__webpack_require__.i) {
/******/ 		__webpack_require__.i.push((options) => {
/******/ 			const originalFactory = options.factory;
/******/ 			options.factory = (moduleObject, moduleExports, webpackRequire) => {
/******/ 				const hasRefresh = typeof self !== "undefined" && !!self.$RefreshInterceptModuleExecution$;
/******/ 				const cleanup = hasRefresh ? self.$RefreshInterceptModuleExecution$(moduleObject.id) : () => {};
/******/ 				try {
/******/ 					originalFactory.call(this, moduleObject, moduleExports, webpackRequire);
/******/ 				} finally {
/******/ 					cleanup();
/******/ 				}
/******/ 			}
/******/ 		})
/******/ 		}
/******/ 	})();
/******/ 	
/******/ 	/* webpack/runtime/compat */
/******/ 	
/******/ 	
/******/ 	// noop fns to prevent runtime errors during initialization
/******/ 	if (typeof self !== "undefined") {
/******/ 		self.$RefreshReg$ = function () {};
/******/ 		self.$RefreshSig$ = function () {
/******/ 			return function (type) {
/******/ 				return type;
/******/ 			};
/******/ 		};
/******/ 	}
/******/ 	
/************************************************************************/
/******/ 	
/******/ 	// startup
/******/ 	// Load entry module and return exports
/******/ 	// This entry module can't be inlined because the eval-source-map devtool is used.
/******/ 	var __webpack_exports__ = __webpack_require__("./worker/index.ts");
/******/ 	
/******/ })()
;