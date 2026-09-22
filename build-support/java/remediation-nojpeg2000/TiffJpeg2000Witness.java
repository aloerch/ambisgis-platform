/* Copyright 2026 AmbisGIS contributors. SPDX-License-Identifier: Apache-2.0 */
import javax.imageio.*;
import javax.imageio.stream.*;
import java.nio.file.*;
public class TiffJpeg2000Witness {
    public static void main(String[] args) throws Exception {
        for(int compression:new int[]{34712,33003,33005}) {
            for(ImageReader reader:new ImageReader[]{new com.sun.media.imageioimpl.plugins.tiff.TIFFImageReaderSpi().createReaderInstance(),new it.geosolutions.imageioimpl.plugins.tiff.TIFFImageReaderSpi().createReaderInstance()}) {
                Path file=Path.of(args[0],"jpeg2000-compression-"+compression+".tif");
                try(ImageInputStream input=ImageIO.createImageInputStream(file.toFile())) {
                    reader.setInput(input);
                    try {reader.read(0);throw new AssertionError("JPEG2000 TIFF unexpectedly decoded " + compression);}
                    catch(javax.imageio.IIOException expected) {
                        if(!expected.getMessage().contains("Unsupported compression"))throw expected;
                        System.out.println("unsupported_tiff_compression="+compression+" reader="+reader.getClass().getName()+" reason="+expected.getMessage());
                    }
                } finally {reader.dispose();}
            }
        }
    }
}
