///** @odoo-module **/
//
//import { registry } from "@web/core/registry";
//import { listView } from "@web/views/list/list_view";
//import { ListController } from "@web/views/list/list_controller";
//
//class StockMoveLineListController extends ListController {}
//
//const StockMoveLineListView = {
//    ...listView,
//    Controller: StockMoveLineListController,
//    props: {
//        ...listView.props,
//    },
//};
//
//registry.category("views").add(
//    "stock_move_line_operation_tree_with_stock",
//    StockMoveLineListView
//);
