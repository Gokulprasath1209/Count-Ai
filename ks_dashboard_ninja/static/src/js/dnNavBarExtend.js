/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { MenuDropdown } from '@web/webclient/navbar/navbar';
import { onWillStart, onWillUnmount, onWillRender, useEffect, onMounted, useRef, onPatched } from "@odoo/owl";
import { NavBar } from "@web/webclient/navbar/navbar";
import { ActionContainer } from "@web/webclient/actions/action_container";
import { ActivityMenu } from "@mail/core/web/activity_menu";
import { UserMenu } from "@web/webclient/user_menu/user_menu";
import { MessagingMenu } from "@mail/core/public_web/messaging_menu";

export function dnNavBarAddClasses(){
    document.querySelector('body')?.classList.add('ks_body_class');
}



export function dnNavBarRemoveClasses(){
    document.querySelector('body')?.classList.remove('ks_body_class');
}


patch(NavBar.prototype,{
   setup(){
       super.setup();
       onMounted( () => {
           let apps_menu_icon = this.root.el?.querySelector('.o_navbar_apps_menu .o-dropdown');
           if(apps_menu_icon)
               apps_menu_icon.innerHTML += `<div class="ks-apps-menu-icon d-none">
                                                <span class="img-bg">
                                                   <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                                                       <path d="M16.475 9.37508H13.1083C11.4333 9.37508 10.625 8.63341 10.625 7.10008V3.31675C10.625 1.78341 11.4417 1.04175 13.1083 1.04175H16.475C18.15 1.04175 18.9583 1.78341 18.9583 3.31675V7.09175C18.9583 8.63341 18.1417 9.37508 16.475 9.37508ZM13.1083 2.29175C11.9917 2.29175 11.875 2.60841 11.875 3.31675V7.09175C11.875 7.80841 11.9917 8.11675 13.1083 8.11675H16.475C17.5917 8.11675 17.7083 7.80008 17.7083 7.09175V3.31675C17.7083 2.60008 17.5917 2.29175 16.475 2.29175H13.1083Z" fill=""/>
                                                       <path d="M16.475 18.9583H13.1083C11.4333 18.9583 10.625 18.1417 10.625 16.475V13.1083C10.625 11.4333 11.4417 10.625 13.1083 10.625H16.475C18.15 10.625 18.9583 11.4417 18.9583 13.1083V16.475C18.9583 18.1417 18.1417 18.9583 16.475 18.9583ZM13.1083 11.875C12.125 11.875 11.875 12.125 11.875 13.1083V16.475C11.875 17.4583 12.125 17.7083 13.1083 17.7083H16.475C17.4583 17.7083 17.7083 17.4583 17.7083 16.475V13.1083C17.7083 12.125 17.4583 11.875 16.475 11.875H13.1083Z" fill=""/>
                                                       <path d="M6.8915 9.37508H3.52484C1.84984 9.37508 1.0415 8.63341 1.0415 7.10008V3.31675C1.0415 1.78341 1.85817 1.04175 3.52484 1.04175H6.8915C8.5665 1.04175 9.37484 1.78341 9.37484 3.31675V7.09175C9.37484 8.63341 8.55817 9.37508 6.8915 9.37508ZM3.52484 2.29175C2.40817 2.29175 2.2915 2.60841 2.2915 3.31675V7.09175C2.2915 7.80841 2.40817 8.11675 3.52484 8.11675H6.8915C8.00817 8.11675 8.12484 7.80008 8.12484 7.09175V3.31675C8.12484 2.60008 8.00817 2.29175 6.8915 2.29175H3.52484Z" fill=""/>
                                                       <path d="M6.8915 18.9583H3.52484C1.84984 18.9583 1.0415 18.1417 1.0415 16.475V13.1083C1.0415 11.4333 1.85817 10.625 3.52484 10.625H6.8915C8.5665 10.625 9.37484 11.4417 9.37484 13.1083V16.475C9.37484 18.1417 8.55817 18.9583 6.8915 18.9583ZM3.52484 11.875C2.5415 11.875 2.2915 12.125 2.2915 13.1083V16.475C2.2915 17.4583 2.5415 17.7083 3.52484 17.7083H6.8915C7.87484 17.7083 8.12484 17.4583 8.12484 16.475V13.1083C8.12484 12.125 7.87484 11.875 6.8915 11.875H3.52484Z" fill=""/>
                                                   </svg>
                                               </span>
                                            </div>`
       });
   },

   async adapt(){
       if(this.currentApp?.xmlid === "ks_dashboard_ninja.board_menu_root" || this.actionService?.currentController?.action.tag === 'ks_dashboard_ninja'){
           if(!document.querySelector('body').classList.contains('ks_body_class'))
               dnNavBarAddClasses();
       }
       else{
           if(document.querySelector('body').classList.contains('ks_body_class'))
               dnNavBarRemoveClasses();
       }
       return super.adapt();
   },

   onNavBarDropdownItemSelection(menu) {
       if(this.currentApp?.xmlid === "ks_dashboard_ninja.board_menu_root"){
            if(!document.body.classList?.contains('ks_body_class')){
               document.querySelector('body').classList.add('ks_body_class')
            }
       }
       else{
           if(document.querySelector('body').classList.contains('ks_body_class'))
               dnNavBarRemoveClasses();
       }
       super.onNavBarDropdownItemSelection(menu);
   }

});

patch(ActionContainer.prototype,{
   setup(){
       super.setup();
       onPatched( () => {
               if(this?.env.services.menu.getCurrentApp?.()?.xmlid === "ks_dashboard_ninja.board_menu_root" || this.info?.componentProps?.action?.tag === 'ks_dashboard_ninja'){
                   if(!document.querySelector('body').classList.contains('ks_body_class'))
                       dnNavBarAddClasses();
               }
               else if(this?.env.services.menu.getCurrentApp?.()?.xmlid !== "ks_dashboard_ninja.board_menu_root" || this.info?.componentProps?.action?.tag !== 'ks_dashboard_ninja'){
                   if(document.querySelector('body').classList.contains('ks_body_class'))
                       dnNavBarRemoveClasses();
               }
       });
   },

});

