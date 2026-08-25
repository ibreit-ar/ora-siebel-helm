// 1. Registro del espacio de nombres
if (typeof (SiebelAppFacade.ContactCardsPR) === "undefined") {
    SiebelJS.Namespace("SiebelAppFacade.ContactCardsPR");

    define("siebel/custom/ContactCardsPR", ["siebel/phyrenderer"], function () {
        SiebelAppFacade.ContactCardsPR = (function () {

            function ContactCardsPR(pm) {
                SiebelAppFacade.ContactCardsPR.superclass.constructor.apply(this, arguments);
            }

            // Heredamos de la clase base PhysicalRenderer
            SiebelJS.Extend(ContactCardsPR, SiebelAppFacade.PhysicalRenderer);

            // --- MÉTODO 1: ShowUI (Preparar el escenario) ---
            ContactCardsPR.prototype.ShowUI = function () {
                SiebelAppFacade.ContactCardsPR.superclass.ShowUI.apply(this, arguments);

                // Obtenemos el ID del contenedor del Applet
                var appletFullId = this.GetPM().Get("GetFullId");
                var $appletContainer = $("#" + appletFullId);

                // Ocultamos la tabla (jqGrid) nativa de Siebel
                $appletContainer.find(".ui-jqgrid").hide();

                // Creamos nuestro contenedor de tarjetas si no existe
                if ($("#cards-container-" + appletFullId).length === 0) {
                    $appletContainer.append("<div id='cards-container-" + appletFullId + "' class='card-view-container'></div>");
                }
            };

            // --- MÉTODO 2: BindData (Dibujar las tarjetas) ---
            ContactCardsPR.prototype.BindData = function () {
                var pm = this.GetPM();
                var appletFullId = pm.Get("GetFullId");
                var $container = $("#cards-container-" + appletFullId);

                // Obtenemos los datos que el servidor envió al navegador
                var recordSet = pm.Get("GetRecordSet");

                $container.empty(); // Limpiamos antes de dibujar

                for (var i = 0; i < recordSet.length; i++) {
                    var record = recordSet[i];

                    // Extraemos los valores (usa los nombres internos de los campos)
                    var fullName = record["First Name"] + " " + record["Last Name"];
                    var jobTitle = record["Job Title"] || "Sin Puesto";
                    var email = record["Email Address"] || "Sin Correo";
                    var initials = (record["First Name"].charAt(0) + record["Last Name"].charAt(0)).toUpperCase();

                    // Construimos el HTML usando las clases de nuestro CSS
                    var cardHtml =
                        "<div class='custom-contact-card' data-index='" + i + "'>" +
                        "<div class='card-avatar-circle'>" + initials + "</div>" +
                        "<h3 class='card-title'>" + fullName + "</h3>" +
                        "<p class='card-subtitle'>" + jobTitle + "</p>" +
                        "<div class='card-body-info'>" +
                        "<div class='card-info-item'><i class='fa fa-envelope'></i> " + email + "</div>" +
                        "</div>" +
                        "<button class='card-action-btn' data-id='" + record["Id"] + "'>Ver Detalle</button>" +
                        "</div>";

                    $container.append(cardHtml);
                }
            };

            // --- MÉTODO 3: BindEvents (Interactividad) ---
            ContactCardsPR.prototype.BindEvents = function () {
                var pm = this.GetPM();
                var appletFullId = pm.Get("GetFullId");

                // Escuchamos el clic en el botón "Ver Detalle"
                $("#cards-container-" + appletFullId).on("click", ".card-action-btn", function () {
                    var rowId = $(this).data("id");

                    // Le decimos a Siebel: "Haz clic en este registro"
                    // Esto dispara la navegación nativa (Drilldown) si está configurado
                    SiebelApp.S_App.ExecuteGlobalObjectManager("InvokeMethod", "DrillDown", {
                        "rowId": rowId
                    });
                });
            };

            return ContactCardsPR;
        }());

        return "SiebelAppFacade.ContactCardsPR";
    });
}