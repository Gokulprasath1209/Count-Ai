/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

class ProductLocationWiseReport extends Component {
    static template = "product_location_wise_report.action";

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            allProducts: [],        // All products for <select>
            products: [],           // Filtered products with stock moves
            selectedProducts: [],   // Expanded products in table
            searchProducts: [],     // Selected product IDs in <select>
        });

        this.toggleProduct = (productId) => {
            const index = this.state.selectedProducts.indexOf(productId);
            if (index >= 0) {
                this.state.selectedProducts.splice(index, 1);
            } else {
                this.state.selectedProducts.push(productId);
            }
        };
//
//        this.onSelectProducts = (ev) => {
//            const selected = Array.from(ev.target.selectedOptions).map(opt => parseInt(opt.value));
//            this.state.searchProducts = selected;
//        };
        this.onSelectProducts = (ev) => {
            const selectedId = parseInt(ev.target.value);
            if (selectedId && !this.state.searchProducts.includes(selectedId)) {
                this.state.searchProducts.push(selectedId);
            }
            ev.target.value = ""; // reset dropdown
             this.loadProducts();
        };

        this.removeProduct = (id) => {
            this.state.searchProducts = this.state.searchProducts.filter(p => p !== id);
             this.loadProducts();
        };

        this.loadProducts = async () => {
            const ids = this.state.searchProducts;
            this.state.products = await this.orm.call(
                "product.location.value",
                "get_products",
                [ids]
            );
        };

        this.loadAllProducts = async () => {
            // Load all products for <select>
            this.state.allProducts = await this.orm.call(
                "product.product",
                "search_read",
                [[], ["id", "display_name"]],
                { limit: 1000 } // adjust as needed
            );
        };

        onWillStart(async () => {
            await this.loadAllProducts();
            await this.loadProducts();
        });
    }

    exportPdf = () => {
        const { jsPDF } = window.jspdf;
        const pdf = new jsPDF("p", "mm", "a4");
        let startY = 10;

        const drawBadge = (pdf, text, x, y, bgColor, textColor = [255, 255, 255]) => {
            pdf.setFontSize(9);
            const paddingX = 2;
            const paddingY = 2;
            const textWidth = pdf.getTextWidth(text) + paddingX * 2;
            const textHeight = 6 + paddingY;
            pdf.setFillColor(...bgColor);
            pdf.rect(x, y - textHeight + 5, textWidth, textHeight, "F");
            pdf.setTextColor(...textColor);
            pdf.text(text, x + paddingX, y);
        };

        this.state.products.forEach((prod) => {
            pdf.setFontSize(12);
            pdf.setTextColor(0, 0, 0);
            pdf.text(`ID: ${prod.id} | Name: ${prod.name} | Ref: ${prod.default_code || "-"}`, 10, startY);
            pdf.text(`Qty Available: ${prod.qty_available}`, 10, startY + 6);

            if (this.state.selectedProducts.includes(prod.id)) {
                let x = 10;
                const y = startY + 16;
                drawBadge(pdf, `MO: ${prod.mo}`, x, y, [0, 123, 255]); x += 35;
                drawBadge(pdf, `SO: ${prod.so}`, x, y, [40, 167, 69]); x += 35;
                drawBadge(pdf, `PO: ${prod.po}`, x, y, [23, 162, 184]); x += 35;
                drawBadge(pdf, `Internal: ${prod.internal}`, x, y, [255, 193, 7], [0, 0, 0]); x += 50;
                drawBadge(pdf, `Scrap: ${prod.scrap}`, x, y, [220, 53, 69]); startY += 28;

                if (prod.recs.length > 0) {
                    pdf.autoTable({
                        startY: startY,
                        head: [["ID", "Reference", "Picking Type", "From", "To", "Qty", "State", "Date"]],
                        body: prod.recs.map(mv => [
                            mv.id, mv.reference, mv.picking_type,
                            mv.location_from, mv.location_to,
                            mv.quantity, mv.state, mv.date
                        ]),
                        theme: "striped",
                        headStyles: { fillColor: [44, 62, 80], textColor: 255, fontSize: 10 },
                        styles: { fontSize: 9, cellPadding: 3 },
                        margin: { left: 10, right: 10 },
                        didDrawPage: (data) => { startY = data.cursor.y + 5; },
                    });
                } else {
                    pdf.setFontSize(9);
                    pdf.setTextColor(100);
                    pdf.text("No stock moves found", 10, startY);
                    startY += 10;
                }
            }

            startY += 15;
            if (startY > pdf.internal.pageSize.getHeight() - 20) {
                pdf.addPage();
                startY = 10;
            }
        });

        pdf.save("dashboard_report_table.pdf");
    };
}

registry.category("actions").add("product_location_wise_report.action", ProductLocationWiseReport);
export default ProductLocationWiseReport;
