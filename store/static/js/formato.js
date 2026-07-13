/*
 * Formato numerico unificado - Formato argentino
 * Criterio unico para toda la app:
 *   - Montos: $14.250,87  (miles con punto, decimal con coma, 2 decimales)
 *   - Cantidad unidad: entero -> 5
 *   - Cantidad fraccionable: 2 decimales -> 5,50
 *
 * Uso:
 *   formatearPeso(14211.22)   -> "$14.211,22"
 *   formatearNumero(14211.22) -> "14.211,22"
 *   parsearNumero("1.230,55") -> 1230.55   (acepta coma o punto)
 *   formatearCantidad(5)      -> "5"
 *   formatearCantidad(5.5)    -> "5,50"
 */

// Convierte un numero a formato argentino (texto): 14250.87 -> "14.250,87"
function formatearNumero(valor, decimales = 2) {
    var num = Number(valor);
    if (isNaN(num)) return "0,00";
    // toLocaleString con es-AR da el formato correcto: 14.250,87
    return num.toLocaleString("es-AR", {
        minimumFractionDigits: decimales,
        maximumFractionDigits: decimales
    });
}

// Monto con simbolo: 14250.87 -> "$14.250,87"
function formatearPeso(valor) {
    return "$" + formatearNumero(valor, 2);
}

// Cantidad inteligente: entero sin decimales, fraccion con 2 decimales
function formatearCantidad(valor) {
    var num = Number(valor);
    if (isNaN(num)) return "0";
    if (Number.isInteger(num)) {
        return String(num);
    }
    return formatearNumero(num, 2);
}

/*
 * PARSEO: convierte el texto que escribe el usuario a un numero.
 * Acepta coma O punto como decimal (transparente para el usuario).
 *
 * Casos que maneja:
 *   "1230,55"    -> 1230.55   (coma decimal)
 *   "1230.55"    -> 1230.55   (punto decimal)
 *   "1.230,55"   -> 1230.55   (punto miles + coma decimal, formato AR)
 *   "1,230.55"   -> 1230.55   (coma miles + punto decimal, formato US)
 *   "1000"       -> 1000      (entero)
 *   ""           -> 0
 */
function parsearNumero(texto) {
    if (texto === null || texto === undefined) return 0;
    var s = String(texto).trim();
    if (s === "") return 0;

    // Quitar el simbolo $ y espacios
    s = s.replace(/\$/g, "").replace(/\s/g, "");

    var tieneComa = s.indexOf(",") !== -1;
    var tienePunto = s.indexOf(".") !== -1;

    if (tieneComa && tienePunto) {
        // Ambos presentes: el ULTIMO que aparece es el decimal
        if (s.lastIndexOf(",") > s.lastIndexOf(".")) {
            // formato AR: 1.230,55  -> quitar puntos (miles), coma es decimal
            s = s.replace(/\./g, "").replace(",", ".");
        } else {
            // formato US: 1,230.55  -> quitar comas (miles), punto es decimal
            s = s.replace(/,/g, "");
        }
    } else if (tieneComa) {
        // Solo coma: es el decimal -> 1230,55 -> 1230.55
        s = s.replace(",", ".");
    }
    // Solo punto o ninguno: ya esta en formato JS, no tocar

    var num = parseFloat(s);
    return isNaN(num) ? 0 : num;
}