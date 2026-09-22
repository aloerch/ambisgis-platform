/* Copyright 2026 AmbisGIS contributors. SPDX-License-Identifier: Apache-2.0 */
import java.awt.image.BufferedImage;
import java.io.ByteArrayOutputStream;
import java.io.FileOutputStream;
import java.nio.file.Path;
import javax.imageio.ImageIO;
import com.lowagie.text.Document;
import com.lowagie.text.Image;
import com.lowagie.text.Rectangle;
import com.lowagie.text.pdf.PdfWriter;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.rendering.PDFRenderer;

/** Real WMS PDF tiles use the requested192x160pixel page at72dpi, with no margins. */
public final class PdfTileFixtures {
    static void write(Path file, byte[] imageBytes) throws Exception {
        try (FileOutputStream stream = new FileOutputStream(file.toFile())) {
            Document doc = new Document(new Rectangle(192, 160), 0, 0, 0, 0);
            PdfWriter.getInstance(doc, stream); doc.open();
            Image image = Image.getInstance(imageBytes);
            image.scaleAbsolute(192, 160); image.setAbsolutePosition(0, 0);
            doc.add(image); doc.close();
        }
    }
    public static void main(String[] args) throws Exception {
        Path target = Path.of(args[0]);
        byte[] jp2 = java.nio.file.Files.readAllBytes(Path.of(args[1]));
        BufferedImage png = new BufferedImage(64, 64, BufferedImage.TYPE_INT_RGB);
        for (int y = 0; y < 64; y++) for (int x = 0; x < 64; x++)
            png.setRGB(x, y, x < 32 ? (30 << 16 | 90 << 8 | 180) : (210 << 16 | 80 << 8 | 30));
        ByteArrayOutputStream bytes = new ByteArrayOutputStream(); ImageIO.write(png, "PNG", bytes);
        write(target.resolve("ordinary-tile.pdf"), bytes.toByteArray());
        write(target.resolve("jp2-tile.pdf"), jp2);
        try (var pdf = Loader.loadPDF(target.resolve("ordinary-tile.pdf").toFile())) {
            BufferedImage image = new PDFRenderer(pdf).renderImageWithDPI(0, 72);
            if (pdf.getNumberOfPages() != 1 || image.getWidth() != 192 || image.getHeight() != 160)
                throw new AssertionError("tile geometry");
            int blue = 0, red = 0;
            for (int y = 0; y < 160; y++) for (int x = 0; x < 192; x++) {
                int rgb = image.getRGB(x, y) & 0xffffff;
                if (rgb == (30 << 16 | 90 << 8 | 180)) blue++;
                if (rgb == (210 << 16 | 80 << 8 | 30)) red++;
            }
            if (blue < 15000 || red < 15000) throw new AssertionError("known tile pixels");
            System.out.println("ordinary_tile pages=1 width=192 height=160 blue=" + blue + " red=" + red);
        }
        try (var pdf = Loader.loadPDF(target.resolve("jp2-tile.pdf").toFile())) {
            var page = pdf.getPage(0);
            if (pdf.getNumberOfPages() != 1 || page.getMediaBox().getWidth() != 192 || page.getMediaBox().getHeight() != 160)
                throw new AssertionError("JPX tile geometry");
            boolean jpx = false;
            for (var name : page.getResources().getXObjectNames()) {
                var object = page.getResources().getXObject(name);
                if (object.getCOSObject().getFilters().toString().contains("JPXDecode")) jpx = true;
            }
            if (!jpx) throw new AssertionError("genuine JPX compressed image missing");
            System.out.println("jpeg2000_tile pages=1 width=192 height=160 JPXDecode=true");
        }
    }
}
