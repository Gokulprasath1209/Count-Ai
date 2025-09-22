/** @odoo-module **/
import {patch} from "@web/core/utils/patch";
import {ActionMenus} from "@web/search/action_menus/action_menus";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
patch(ActionMenus.prototype, {
  setup(...args) {
    super.setup(...args);
    this.user = user
  },
  async getActionItems(props) {
    let result = await super.getActionItems(...arguments)
    let hide_delete = await this.user.hasGroup('hide_delete_option.group_hide_delete')
    if (hide_delete) {
      result = result.filter(item => item.key !== 'delete');
    }
    return result
  }
});
