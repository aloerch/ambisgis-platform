/** Run the retained publisher line-join regression only after exact renderer proof. */
public class NativeRenderingWitness {
 public static void main(String[] args) throws Exception {
  RenderingWitness.main(new String[]{System.getProperty("ambisgis.witness.renderer"),System.getProperty("ambisgis.witness.renderer.sha256")});
  JoinMiterRedundantLineSegmentsTest.main(new String[0]);
 }
}
