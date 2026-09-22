/* Actual returned PDF parsing/rendering witness, using the selected WAR PDFBox. */
import java.io.File;
import javax.imageio.ImageIO;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.rendering.PDFRenderer;

public class PrintPdfWitness {
    public static void main(String[] args) throws Exception {
        try (PDDocument document = Loader.loadPDF(new File(args[0]))) {
            if (document.getNumberOfPages() != 1) throw new AssertionError("expected exactly one printed page");
            if (!ImageIO.write(new PDFRenderer(document).renderImageWithDPI(0, 72), "PNG", new File(args[1])))
                throw new AssertionError("PNG render writer unavailable");
        }
        System.out.println("PASS actual returned PDF parsed and rendered");
    }
}
