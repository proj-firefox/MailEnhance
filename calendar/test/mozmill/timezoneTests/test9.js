/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

var calUtils = require("../shared-modules/calendar-utils");
var timezoneUtils = require("../shared-modules/timezone-utils");

const sleep = 500;
var calendar = "Mozmill";
var dates = [[2009,  1,  1], [2009,  4,  2], [2009,  4, 16], [2009,  4, 30],
             [2009,  7,  2], [2009, 10, 15], [2009, 10, 29], [2009, 11,  5]];
var timezones = ["America/St_Johns", "America/Caracas", "America/Phoenix", "America/Los_Angeles",
                 "America/Argentina/Buenos_Aires", "Europe/Paris", "Asia/Kathmandu", "Australia/Adelaide"];
/* rows - dates
   columns - correct time for each event */
var times = [[[13, 45], [14, 45], [15, 45], [16, 45], [17, 45], [18, 45], [19, 45], [20, 45]],
             [[12, 45], [14, 45], [15, 45], [15, 45], [17, 45], [17, 45], [19, 45], [20, 45]],
             [[12, 45], [14, 45], [15, 45], [15, 45], [17, 45], [17, 45], [19, 45], [21, 45]],
             [[12, 45], [14, 45], [15, 45], [15, 45], [17, 45], [17, 45], [19, 45], [21, 45]],
             [[12, 45], [14, 45], [15, 45], [15, 45], [17, 45], [17, 45], [19, 45], [21, 45]],
             [[12, 45], [14, 45], [15, 45], [15, 45], [17, 45], [17, 45], [19, 45], [20, 45]],
             [[12, 45], [14, 45], [15, 45], [15, 45], [17, 45], [18, 45], [19, 45], [20, 45]],
             [[13, 45], [14, 45], [15, 45], [16, 45], [17, 45], [18, 45], [19, 45], [20, 45]]]

var setupModule = function(module) {
  controller = mozmill.getMail3PaneController();
}

var testTimezones9_checkKathmandu = function () {
  let eventPath = '/{"tooltip":"itemTooltip","calendar":"' + calendar.toLowerCase() + '"}';
  
  controller.click(new elementslib.ID(controller.window.document, "calendar-tab-button"));
  calUtils.switchToView(controller, "day");
  calUtils.goToDate(controller, 2009, 1, 1);
  
  timezoneUtils.verify(controller, dates, timezones, times);
}

var teardownTest = function(module) {
  timezoneUtils.switchAppTimezone(timezones[7]);
}
